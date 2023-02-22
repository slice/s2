"""Mafia game."""

__all__ = ["MafiaGame", "MafiaGameState"]

import asyncio
import datetime
import enum
import logging
import random
from typing import (
    cast,
    Any,
    AsyncGenerator,
    Dict,
    Optional,
    Set,
    Type,
    Union,
    Iterator,
)

import discord
from discord.http import HTTPClient, Route
import lifesaver
from lifesaver.utils.formatting import codeblock

from . import messages
from . import role
from .permissions import ALLOW, BLOCK, HUSH, HUSH_PERMS, NEUTRAL_HUSH_PERMS
from .player import Player
from .role import AnyRoleType, Role, RoleActionContext
from .roster import Roster
from .lobby import LobbyMenu
from .memory import Memory, Key
from .utils import basic_command
from .formatting import mention_set, user_listing, msg
from .voting import trial_and_judgement_loop


class MafiaGameState(enum.Enum):
    """A :class:`enum.Enum` representing possible game states."""

    #: Waiting for people to join the game.
    WAITING = enum.auto()

    #: Waiting for people to join the game guild.
    FILLING = enum.auto()

    #: The game has started.
    STARTED = enum.auto()


class EndGame(RuntimeError):
    """Exception that ends the game from within the ``_game_loop``."""


class MafiaGame:
    """A class representing a game of mafia."""

    WEIGHTED_ROLES: Dict[AnyRoleType, int] = {
        role.Innocent: 10,
        role.Investigator: 10,
        role.Doctor: 10,
        role.Medium: 5,
    }

    def __init__(
        self,
        bot: lifesaver.Bot,
        *,
        creator: discord.Member,
        lobby_channel: Optional[discord.TextChannel] = None,
        ctx: lifesaver.Context,
    ):
        self.bot = bot

        #: The :class:`lifesaver.Context` that created this game.
        self._ctx = ctx

        #: The set of all game participants as Discord members of the original
        #: server.
        self.participants: Set[discord.Member] = {creator}

        #: The game roster. Stores the full list of active players.
        self.roster: Optional[Roster] = None

        #: The user who created the game.
        self.creator = creator

        #: The channel that the lobby was created in.
        self.lobby_channel = lobby_channel or ctx.channel

        #: The logger.
        self.log = logging.getLogger(f"{__name__}[{self.lobby_channel.id}]")
        self.log.setLevel(logging.DEBUG)

        #: The invitation message in the lobby.
        self.invite_message: Optional[discord.Message] = None

        #: The main text channel where both mafia and townies can speak during the day.
        self.all_chat: Optional[discord.TextChannel] = None

        #: The dictionary of grouped role chats for each role in the game.
        self.role_chats: Dict[AnyRoleType, discord.TextChannel] = {}

        #: The dictionary of personal chats for each player in the game.
        self.personal_chats: Dict[Player, discord.TextChannel] = {}

        #: The memory dictionary. Used to track state from actions performed at
        #: night.
        self.memory = Memory()

        #: The lock for role states.
        self._memory_lock = asyncio.Lock()

        #: The guild where the game is taking place.
        self.guild: Optional[discord.Guild] = None

        #: The role for spectators.
        self.spectator_role: Optional[discord.Role] = None

        #: The role for dead players.
        self.dead_role: Optional[discord.Role] = None

        #: The role for all players, dead or alive.
        self.player_role: Optional[discord.Role] = None

        #: The current state of the game.
        self.state = MafiaGameState.WAITING

        #: The current day.
        self.day = 1

        #: The current time of day.
        self.daytime = True

        #: Whether the game was thrown.
        self.thrown = False

        #: The lobby menu. Controls player joining and leaving, and game starting.
        self._lobby_menu: Optional[LobbyMenu] = None

        #: The game loop.
        self._game_loop_task: Optional[asyncio.Task[None]] = None

        #: An event that is set when all players have joined the game guild.
        self._all_players_joined = asyncio.Event()

        #: The message that shows who still needs to join.
        self._filling_message: Optional[discord.Message] = None

        #: Whether we are handling nocturnal actions or not.
        self._handling_nocturnal_actions: bool = False

        #: The message showing the list of roles.
        self._role_listing_message: Optional[discord.Message] = None

    #: Debugging mode. Shortens some wait times.
    DEBUG = False

    @property
    def category(self) -> discord.CategoryChannel:
        """Return the "mafia" guild category."""
        assert self.guild is not None
        return self.guild.categories[0]

    async def on_member_join(self, member: discord.Member) -> None:
        """Handle a member join."""
        assert self.guild is not None
        assert self.player_role is not None
        assert self.roster is not None

        self.log.info("joined: %s (%d)", member, member.id)

        # check if this member is actually a player, but they have already died
        is_already_dead = (
            player := self.roster.get_player(member)
        ) is not None and player.dead

        if is_already_dead:
            assert self.dead_role is not None
            await member.add_roles(self.dead_role)
            return

        if member not in self.participants:
            assert self.spectator_role is not None
            await member.add_roles(self.spectator_role)
            return

        await member.add_roles(self.player_role)
        await self.grant_channel_access(member)

        if all(participant in self.guild.members for participant in self.participants):
            # everyone has joined!
            self._all_players_joined.set()
        else:
            # more still need to join...
            await self._update_filling_message()

    async def on_member_remove(self, member: discord.Member) -> None:
        """Handle a game member leaving the guild."""
        assert self.roster is not None

        if (player := self.roster.get_player(member)) is None:
            return

        if player.dead or self.thrown:
            return

        self.thrown = True
        await self.throw(player)

    async def on_message(self, message: discord.Message) -> None:
        """Handle a message being sent in the guild."""
        await self._handle_always_available_commands(message)

        if self._handling_nocturnal_actions:
            await self._handle_night_command(message)

    async def _all_messages(self) -> AsyncGenerator[discord.Message, None]:
        """Asynchronously iterate over all new messages in the guild."""

        def check(message: discord.Message) -> bool:
            return message.guild == self.guild

        while True:
            yield await self.bot.wait_for("message", check=check)

    async def _messages_in(
        self,
        channel: discord.TextChannel,
        *,
        by: Union[Set[discord.Member], discord.Member],
    ) -> AsyncGenerator[discord.Message, None]:
        """Asynchronously iterate over specific messages in the guild."""

        def check(message: discord.Message) -> bool:
            channel_cond = message.channel == channel
            if isinstance(by, set):
                return channel_cond and message.author in by
            else:
                return channel_cond and message.author == by

        while True:
            yield await self.bot.wait_for("message", check=check)

    async def throw(self, thrower: Player) -> None:
        assert self.all_chat is not None

        await self._unlock()
        await self.all_chat.send(msg(messages.GAME_THROWN, thrower=thrower))

        if (task := self._game_loop_task) is None:
            # the game hasn't even started yet
            await self.game_over()
        else:
            task.cancel()

    async def gather_participants(self) -> bool:
        """Interactively gather game participants."""
        self.log.info("creating lobby menu")

        self._lobby_menu = menu = LobbyMenu(game=self)
        await menu.start(self._ctx, channel=self.lobby_channel, wait=True)
        await menu.message.delete()
        return not menu.was_cancelled

    async def _setup_game_area(self) -> None:
        """Create and prepare the game area."""
        try:
            date = datetime.datetime.utcnow().strftime("%m/%d %H:%M")
            guild = self.guild = await self.bot.create_guild(name=f"mafia {date}")
        except discord.HTTPException as err:
            raise RuntimeError("failed to create guild") from err

        # set default notifications to mentions only
        http = self.bot.http  # type: ignore
        await cast(HTTPClient, http).request(
            Route("PATCH", "/guilds/{guild_id}", guild_id=guild.id),
            json={"default_message_notifications": 1},
        )

        # restrict the default set of permissions so that people can't cause
        # any trouble...
        base_permissions = discord.Permissions()
        for permission in {
            # voice
            # "connect",
            "stream",
            "speak",
            "use_voice_activation",
            # messages
            "add_reactions",
            "read_messages",
            "send_messages",
            "embed_links",
            "attach_files",
            "external_emojis",
            "read_message_history",
        }:
            setattr(base_permissions, permission, True)
        await guild.default_role.edit(permissions=base_permissions)

        # refresh cache
        await asyncio.sleep(1)
        guild = self.guild = cast(discord.Guild, self.bot.get_guild(guild.id))

        # rename the default category just for fun
        first_category = guild.categories[0]
        await first_category.edit(name="mafia")

        # delete voice-related stuff
        voice_category = guild.categories[1]
        await voice_category.delete()
        await guild.voice_channels[0].delete()

        # use the default text channel as the game chat
        all_chat = self.all_chat = guild.text_channels[0]
        await all_chat.edit(name="game-chat")

        spectator_role = self.spectator_role = await guild.create_role(
            name="spectator", color=discord.Color.dark_grey()
        )
        dead_role = self.dead_role = await guild.create_role(
            name="dead", color=discord.Color.dark_red(), hoist=True
        )
        player_role = self.player_role = await guild.create_role(
            name="player", color=discord.Color.default(), hoist=True
        )
        await spectator_role.edit(position=1)
        await dead_role.edit(position=2)
        await player_role.edit(position=3)

        # apply overwrites
        await all_chat.edit(overwrites={dead_role: HUSH, spectator_role: HUSH})

        self.spectator_chat = await first_category.create_text_channel(
            name="spec-chat",
            overwrites={
                guild.default_role: BLOCK,
                spectator_role: ALLOW,
                dead_role: ALLOW,
            },
        )

    async def _handle_always_available_commands(self, message: discord.Message) -> None:
        """Handle commands that are always available."""
        assert self.roster is not None
        player = self.roster.get_player(message.author)

        if player is None:
            return

        will_text = basic_command("!will", message.content)
        if will_text:
            assert player.channel is not None
            if len(will_text) > 1000:
                await player.channel.send(
                    f"{player.mention}: That's too long. 1,000 characters max."
                )
            else:
                await player.channel.send(f"{player.mention}: OK, saved your will.")
                player.will = will_text
            return

    async def _handle_night_command(self, message: discord.Message) -> None:
        """Handle commands from personal and grouped role channels at night."""
        assert self.roster is not None

        player = self.roster.get_player(message.author)

        if player is None:
            return

        if player.role.grouped and message.channel != self.role_chats[player.role]:
            # for a player in a grouped role, only allow processing when
            # speaking in the designated channel
            return

        # grab previous state
        prev_state = None
        if (key := player.role.localized_key(player)) is not None:
            prev_state = self.memory.get(key)

        ctx = RoleActionContext(game=self, player=player, message=message)
        new_state = await player.role.on_message(ctx, prev_state)

        # update role state from on_message if the state has changed
        if key is not None and new_state != prev_state:
            self.log.debug("updating %r to %r", key, new_state)
            async with self._memory_lock:
                self.memory[key] = new_state

    async def _nighttime(self) -> None:
        assert self.roster is not None
        assert self.all_chat is not None

        # we have already locked back in the game loop
        # await self._lock()

        # dump the previous role state
        self.memory.reset()

        def iter_nocturnal(*, priority_by: str) -> Iterator[Player]:
            assert self.roster is not None

            # for players in grouped roles, only handle one player per grouped
            # role. this makes the event handlers only trigger once a night.
            handled_grouped_roles: Set[AnyRoleType] = set()

            nocturnal = sorted(
                self.roster.nocturnal,
                key=lambda player: getattr(player.role, priority_by)._listener_priority,
                reverse=True,
            )

            for player in nocturnal:
                if player.role in handled_grouped_roles or player.dead:
                    continue
                self.log.debug("%s: yielding", player)
                yield player
                if player.role.grouped:
                    handled_grouped_roles.add(player.role)

        def get_state() -> Optional[Any]:
            if (key := player.role.localized_key(player)) is not None:
                return self.memory.get(key)
            return None

        for player in iter_nocturnal(priority_by="on_night_begin"):
            ctx = RoleActionContext(game=self, player=player)

            # persistent memory means that sometimes we pass non-None state to
            # on_night_begin (we reset it above)
            state = get_state()

            self.log.debug(
                "on_night_begin: %s (%s), state=%r", player, player.role.name, state
            )
            await player.role.on_night_begin(ctx, state)

        # handle actions from nocturnal players, such as the mafia choosing who
        # to kill. at the end of the night, the state from these actions will
        # be "carried out".
        self.log.debug("handling nocturnal actions")
        self._handling_nocturnal_actions = True
        await asyncio.sleep(10 if self.DEBUG else 36)
        self._handling_nocturnal_actions = False

        # now to carry out what decisions were made during the night...
        for player in iter_nocturnal(priority_by="on_night_end"):
            self.log.debug("%s: handling end event", player)

            state = get_state()
            ctx = RoleActionContext(game=self, player=player)
            self.log.debug(
                "on_night_end: %s (%s), state=%r", player, player.role.name, state
            )
            await player.role.on_night_end(ctx, state)

        await asyncio.sleep(3)

        # unlock during day instead, after the death has been announced
        # await self._unlock()

    async def alltalk(self) -> None:
        """Allow all game participants to speak in the main game channel."""
        assert self.all_chat is not None
        assert self.dead_role is not None
        assert self.spectator_role is not None
        await self.all_chat.set_permissions(self.dead_role, **NEUTRAL_HUSH_PERMS)
        await self.all_chat.set_permissions(self.spectator_role, **NEUTRAL_HUSH_PERMS)

    async def _notify_roles(self) -> None:
        """Notify everyone of their role in the game."""
        assert self.all_chat is not None
        assert self.roster is not None

        for player in self.roster.players:
            assert player.channel is not None
            if (greeting := messages.ROLE_GREETINGS.get(player.role.name)) is not None:
                await player.channel.send(f"{player.mention}: {msg(greeting)}")

        mafia_chat = self.role_chats[role.Mafia]
        await mafia_chat.send(
            msg(messages.MAFIA_GREET, flavor=msg(messages.MAFIA_GREET_FLAVOR))
        )

    async def grant_channel_access(self, member: discord.Member) -> None:
        """Grant a member access to the channels that they need access to."""
        assert self.roster is not None

        player = self.roster.get_player(member.id)
        assert player is not None
        assert player.channel is not None
        await player.channel.set_permissions(member, overwrite=ALLOW)

        if player.role.grouped:
            role_channel = self.role_chats[player.role]
            await role_channel.set_permissions(member, overwrite=ALLOW)

    async def _lock(self) -> None:
        """Prevent anyone from sending messages in the game channel."""
        assert self.all_chat is not None
        assert self.guild is not None
        await self.all_chat.set_permissions(self.guild.default_role, **HUSH_PERMS)  # type: ignore  # noqa

    async def _unlock(self) -> None:
        """Undo a lock."""
        assert self.all_chat is not None
        assert self.guild is not None
        await self.all_chat.set_permissions(
            self.guild.default_role, **NEUTRAL_HUSH_PERMS
        )

    async def _game_over(self, *, mafia_won: bool) -> None:
        """Send the list of alive players and activate alltalk."""
        assert self.all_chat is not None
        assert self.roster is not None

        header_msg: str
        listing_msg: str

        if mafia_won:
            header_msg = messages.MAFIA_WIN
            listing_msg = messages.CURRENTLY_ALIVE_MAFIA
        else:
            header_msg = messages.TOWNIES_WIN
            listing_msg = messages.CURRENTLY_ALIVE_TOWNIES

        alive = self.roster.alive_mafia if mafia_won else self.roster.alive_townies
        alive_members = {player.member for player in alive}

        await self._update_role_listing(show_players=True)

        msgs = [
            msg(header_msg),
            msg(listing_msg, players=user_listing(alive_members, commas=True)),
            msg(
                messages.PLAYER_ROLE_LISTING,
                players=self.role_listing(show_players=True),
            ),
            msg(messages.THANK_YOU),
        ]

        await self.all_chat.send("\n\n".join(msgs))

        await asyncio.sleep(2)
        await self._unlock()
        await self.alltalk()
        await asyncio.sleep(10)

    async def _display_will(
        self, player: Player, channel: Optional[discord.TextChannel] = None
    ) -> None:
        if player.will is None:
            return

        assert self.all_chat is not None
        channel = channel or self.all_chat
        await channel.send(f"{player}'s will:\n\n" + codeblock(player.will))
        await asyncio.sleep(5)

    def _role_reveal(self, player: Player, *, pronoun: bool = False) -> discord.Embed:
        title = (
            msg(messages.THEY_ROLE, role=player.role.name)
            if pronoun
            else msg(messages.WAS_ROLE, died=player, role=player.role.name)
        )

        return discord.Embed(
            title=title,
            color=(discord.Color.red() if player.role.evil else discord.Color.green()),
        )

    async def _check_game_over(self) -> None:
        assert self.roster is not None

        if self.roster.all_mafia_dead():
            await self._game_over(mafia_won=False)
            raise EndGame()
        elif self.roster.all_townies_dead():
            await self._game_over(mafia_won=True)
            raise EndGame()

    async def _daytime(self) -> None:
        assert self.all_chat is not None
        assert self.roster is not None

        if (victim := self.memory.get(Key("mafia_victim"))) is not None and victim.dead:
            await self.all_chat.send(msg(messages.FOUND_DEAD, victim=victim))
            await asyncio.sleep(3)
            await self._display_will(victim)
            await self.all_chat.send(embed=self._role_reveal(victim, pronoun=True))
            await self._update_role_listing()
            await asyncio.sleep(5)

        await self._check_game_over()

        # unlock from being locked during night
        await self._unlock()

        # time to discuss + vote
        discussion_time = 5 if self.DEBUG else 45

        await self.all_chat.send(msg(messages.DISCUSSION_TIME_ANNOUNCEMENT))
        await asyncio.sleep(discussion_time)

        # time to accuse and judge people
        await trial_and_judgement_loop(self)

        await self._check_game_over()

    async def _game_loop(self) -> None:
        assert self.all_chat is not None
        assert self.roster is not None

        # hello, everybody!
        await self.all_chat.send(
            msg(messages.GAME_START, mentions=mention_set(self.roster.players))
        )
        await asyncio.sleep(5)

        while True:
            if not self.daytime:
                # it's night; prevent people from speaking as early as possible
                # this will be unlocked during the day
                await self._lock()

            # send current day state to players
            day_state = msg(
                messages.DAY_ANNOUNCEMENT
                if self.daytime
                else messages.NIGHT_ANNOUNCEMENT,
                day=self.day,
            )

            if not self.daytime:
                # need some personality
                day_state += "\n\n" + msg(messages.NIGHT_FLAVOR)

            await self.all_chat.send(day_state)

            self.log.info(
                "time progression; day %d, daytime=%s", self.day, self.daytime
            )

            # if we are on d1, send some directions and just move onto n1.
            if self.daytime and self.day == 1:
                mafia_n = len(self.roster.mafia)
                await self.all_chat.send(msg(messages.TUTORIAL, mafia_n=mafia_n))
                await asyncio.sleep(3 if self.DEBUG else 15)
                self.daytime = False
                continue

            try:
                if self.daytime:
                    await self._daytime()
                else:
                    await self._nighttime()
            except EndGame:
                break

            if not self.daytime:
                # it's night, so move onto next
                self.day += 1
                self.daytime = True
            else:
                # it's day, so move onto night
                self.daytime = False

    async def _update_filling_message(self) -> None:
        assert self.guild is not None
        assert self.all_chat is not None
        assert self.roster is not None

        not_joined = self.participants - set(self.guild.members)
        text = msg(messages.FILLING_PROGRESS, waiting_on=user_listing(not_joined))

        if self._filling_message is None:
            self._filling_message = await self.all_chat.send(text)
        else:
            await self._filling_message.edit(content=text)

    def role_listing(self, *, show_players: bool = False) -> str:
        """Generate a listing of all roles in the game.

        You may also optionally show players' names adjacent to their roles.
        """
        assert self.roster is not None

        def _format_player(player: Player) -> str:
            named_entity = (
                f"{player}: {player.role.name}" if show_players else player.role.name
            )

            if player.dead:
                named_entity = f"~~{named_entity}~~"

            line = "\N{WHITE SMALL SQUARE} " + named_entity

            return line

        sorted_players = sorted(
            self.roster.players, key=lambda player: player.role.name
        )
        return "\n".join(map(_format_player, sorted_players))

    async def _update_role_listing(self, *, show_players: bool = False) -> None:
        assert self.all_chat is not None

        header = "Players" if show_players else "Roles"
        listing = header + ":\n\n" + self.role_listing(show_players=show_players)

        if self._role_listing_message is None:
            self._role_listing_message = await self.all_chat.send(listing)
            await self._role_listing_message.pin()
        else:
            await self._role_listing_message.edit(content=listing)

    async def _setup_players_and_roster(self) -> None:
        assert self.guild is not None
        assert self.dead_role is not None

        # create a player object for each participant, defaulting to inno
        player_set = {
            Player(participant, role=role.Innocent, game=self)
            for participant in self.participants
        }

        # create the main roster
        self.roster = roster = Roster(self, player_set)
        self.log.info("initial roster: %r", roster)

        # assign the mafia
        mafia = roster.sample(role.Mafia.n_players(roster))
        for maf in mafia:
            maf.role = role.Mafia

        # assign the rest of the roles
        wr_roles = list(self.WEIGHTED_ROLES.keys())
        wr_weights = list(self.WEIGHTED_ROLES.values())

        for townie in roster.townies:
            chosen_role: Type[Role[Any]] = random.choices(wr_roles, weights=wr_weights)[
                0
            ]
            townie.role = chosen_role

        if all(townie.role is role.Innocent for townie in roster.townies):
            # all are innocent, oh no! force an investigator
            lucky_townie = random.choice(list(roster.townies))
            lucky_townie.role = role.Investigator

        self.log.info("assigned roles: %r", roster)

        # create personal channels for everyone
        for player in player_set:
            overwrites: Dict[
                Union[discord.Role, discord.Member], discord.PermissionOverwrite
            ] = {
                self.guild.default_role: BLOCK,
                self.dead_role: HUSH,
                # can't overwrite until they join...
            }
            channel = await self.category.create_text_channel(
                name=f"player-{player.id}", overwrites=overwrites,
            )
            player.channel = channel

        # create grouped channels for the roles that need it
        grouped_roles = {player.role for player in player_set if player.role.grouped}
        for grouped_role in grouped_roles:
            channel_name = f"{grouped_role.name.lower()}-chat"
            self.role_chats[grouped_role] = await self.category.create_text_channel(
                name=channel_name,
                overwrites={self.guild.default_role: BLOCK, self.dead_role: HUSH},
            )

        self.log.debug("role_chats: %r", self.role_chats)

    async def start(self) -> None:
        """Gather participants and start the game."""
        self.log.info("game starting...")

        success = await self.gather_participants()
        if not success:
            self.log.info("game was aborted")
            return

        self.log.info("we have enough players, setting up game area")
        await self.lobby_channel.send("setting up game area... just 1 moment...")
        try:
            await self._setup_game_area()
        except Exception as err:
            self.log.exception("failed to setup game area")
            await self.lobby_channel.send(
                f"{self.bot.tick(False)} failed to setup game area: `{err}`"
            )
            return

        assert self.guild is not None
        assert self.all_chat is not None

        await self._setup_players_and_roster()
        assert self.roster is not None
        await self._update_role_listing()

        invite = await self.all_chat.create_invite()
        self.invite_message = await self.lobby_channel.send(
            content=msg(
                messages.LOBBY_INVITE,
                mentions=mention_set(self.participants),
                invite=invite,
            )
        )

        self.state = MafiaGameState.FILLING
        await self._update_filling_message()
        await self._all_players_joined.wait()

        assert self._filling_message is not None
        await self._filling_message.delete()
        await self.roster.localize()

        await self._notify_roles()
        await asyncio.sleep(5)

        self.state = MafiaGameState.STARTED
        self._game_loop_task = asyncio.create_task(self._game_loop())

        try:
            await self._game_loop_task
        except asyncio.CancelledError:
            self.log.info("game was cancelled, proceeding as normal")
        except Exception as err:
            self.log.exception("error during main game loop")
            await self.all_chat.send(msg(messages.SOMETHING_BROKE, error=err))

        await self.game_over()

    async def game_over(self) -> None:
        """Delete the guild after waiting for a bit."""
        assert self.guild is not None
        assert self.all_chat is not None

        await self.all_chat.send(msg(messages.GAME_OVER, seconds=15))
        await asyncio.sleep(15)

        await self.guild.delete()

        try:
            assert self.invite_message is not None
            listing = self.role_listing(show_players=True)
            await self.invite_message.edit(
                content=msg(messages.GAME_OVER_INVITE, players=listing)
            )
        except discord.HTTPException:
            pass
