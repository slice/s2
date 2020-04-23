"""Mafia game."""

__all__ = ["MafiaGame", "MafiaGameState"]

import asyncio
import collections
import datetime
import enum
import logging
import math
import random
import typing
from typing import (DefaultDict, Dict, List, Optional, Sequence, Set, Tuple,
                    Union)

import discord
import fuzzywuzzy.process as fw_process

from lifesaver.utils import pluralize

from . import messages
from .roster import Roster

BLOCK = discord.PermissionOverwrite(read_messages=False)
ALLOW = discord.PermissionOverwrite(read_messages=True)
HUSH_PERMS: Dict[str, bool] = {"add_reactions": False, "send_messages": False}
HUSH = discord.PermissionOverwrite(**HUSH_PERMS)
NEUTRAL_HUSH_PERMS = {key: None for key in HUSH_PERMS}


def mention_set(users: typing.AbstractSet[discord.User]) -> str:
    """Format a list of mentions from a list of users."""
    return ", ".join(user.mention for user in users)


def basic_command(name: str, inp: str) -> Optional[str]:
    name = name + " "

    if not inp.startswith(name):
        return None
    return inp[len(name) :]


def select_member(
    selector: str, members: Set[discord.Member]
) -> Optional[discord.Member]:
    direct_match = discord.utils.find(
        lambda member: str(member).lower() == selector.lower()
        or member.name.lower() == selector.lower()
        or str(member.id) == selector,
        members,
    )

    if direct_match is not None:
        return direct_match

    mapping = {member.id: member.name for member in members}
    _, score, selected_id = fw_process.extractOne(selector, mapping)

    if score > 50:  # arbitrary threshold
        return discord.utils.find(lambda member: member.id == selected_id, members)

    return None


def user_listing(users: Union[Sequence[discord.User], Set[discord.User]]) -> str:
    """Format a list of users."""
    return "\n".join(f"\N{EM DASH} {user}" for user in users)


def msg(message: Union[str, List[str]], *args, **kwargs) -> str:
    """Process a message, randomly choosing from it if it's a ``list``."""
    if isinstance(message, list):
        message = random.choice(message)
    return message.format(*args, **kwargs)


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

    def __init__(
        self, bot, *, creator: discord.Member, lobby_channel: discord.TextChannel
    ):
        self.bot = bot
        self.log = logging.getLogger(f"{__name__}[{lobby_channel.id}]")

        #: The game roster, a class that stores full lists of players and handles
        #: mafia selection.
        self.roster = Roster(self, creator=creator)

        #: The user who created the game.
        self.creator = creator

        #: The channel that the lobby was created in.
        self.lobby_channel = lobby_channel

        #: The main text channel where both mafia and townies can speak during the day.
        self.all_chat: Optional[discord.TextChannel] = None

        #: The text channel reserved for mafia members.
        self.mafia_chat: Optional[discord.TextChannel] = None

        #: The text channel reserved for spectators and dead players.
        self.spectator_chat: Optional[discord.TextChannel] = None

        #: The text channel reserved for the investigator.
        self.gator_house: Optional[discord.TextChannel] = None

        #: The investigator's target for tonight.
        self.gator_visiting: Optional[discord.Member] = None

        #: The guild where the game is taking place.
        self.guild: Optional[discord.Guild] = None

        #: The role for spectators.
        self.spectator_role: Optional[discord.Role] = None

        #: The role for dead players.
        self.dead_role: Optional[discord.Role] = None

        #: The current state of the game.
        self.state = MafiaGameState.WAITING

        #: The current day.
        self.day = 1

        #: The current time of day.
        self.daytime = True

        #: A mapping of hanging votes during the daytime.
        #: The key is the user ID of the person to hang, while the value is the
        #: list of users who voted for that person to be hanged.
        self.hanging_votes: DefaultDict[int, list] = collections.defaultdict(list)

        #: The victim that will be killed tonight, as decided by mafia.
        self.victim_tonight: Optional[discord.Member] = None

        #: Whether the game was thrown.
        self.thrown = False

        #: The game loop.
        self._game_loop_task: Optional[asyncio.Task] = None

        #: An event that is set when all players have joined the game guild.
        self._players_joined_event = asyncio.Event()

        #: The message that shows who still needs to join.
        self._filling_message: Optional[discord.Message] = None

    #: Debugging mode. Shortens some wait times.
    DEBUG = False

    @property
    def category(self) -> discord.CategoryChannel:
        """Return the "mafia" guild category."""
        assert self.guild is not None
        return self.guild.categories[0]

    @property
    def _listeners(self):
        return {
            "on_member_join": self._member_join,
            "on_member_remove": self._member_remove,
        }

    def _attach_listeners(self) -> None:
        for name, func in self._listeners.items():
            self.bot.add_listener(func, name)

    def _detach_listeners(self) -> None:
        for name, func in self._listeners.items():
            self.bot.remove_listener(func, name)

    async def _member_join(self, member: discord.Member) -> None:
        if member.guild != self.guild:
            return

        self.log.info("joined: %s (%d)", member, member.id)

        if member not in self.roster.all:
            # someone not in the roster joined, give spectator role
            await member.add_roles(self.spectator_role)
            return

        if set(self.guild.members) >= self.roster.all:
            # everyone has joined!
            self._players_joined_event.set()
        else:
            # more still need to join...
            await self._update_filling_message()

    async def _member_remove(self, member: discord.Member) -> None:
        if member.guild != self.guild:
            return

        # make sure they are a player before throwing
        if member not in self.roster.all:
            return

        if self.thrown:
            return

        self.thrown = True
        await self._throw(member)

    async def _messages_in(
        self,
        channel: discord.TextChannel,
        *,
        by: Union[Set[discord.Member], discord.Member],
    ) -> typing.AsyncGenerator[discord.Message, None]:
        def check(message: discord.Message) -> bool:
            channel_cond = message.channel == channel
            if isinstance(by, set):
                return channel_cond and message.author in by
            else:
                return channel_cond and message.author == by

        while True:
            message = await self.bot.wait_for("message", check=check)
            yield message

    async def _throw(self, thrower) -> None:
        assert self.all_chat is not None

        # cancel game from proceeding any further
        if self._game_loop_task is not None:
            self._game_loop_task.cancel()

        await self._unlock()
        await self.all_chat.send(
            msg(messages.GAME_THROWN, mentions="@everyone", thrower=thrower)
        )

        if self._game_loop_task is None:
            # game hasn't even started, so we need to call goodbye ourselves
            await self._goodbye()

    async def _gather_players(self) -> bool:
        """Interactively gather game participants."""
        self.log.info("gathering players for game")
        bare_minimum = 3
        lobby = self.lobby_channel

        def embed() -> str:
            required = 3 - len(self.roster.all)
            required_text = pluralize(player=required, with_indicative=True)

            embed = discord.Embed(
                title="Mafia Lobby",
                description=user_listing(self.roster.all),
                color=discord.Color.gold(),
            )
            embed.set_author(name=str(self.creator), icon_url=self.creator.avatar_url)
            if required > 0:
                embed.set_footer(text=f"{required_text} required")
            return embed

        join_emoji = "\N{RAISED HAND WITH FINGERS SPLAYED}"
        start_emoji = "\N{WHITE HEAVY CHECK MARK}"
        abort_emoji = "\N{CROSS MARK}"

        prompt = await lobby.send(
            msg(messages.LOBBY_CREATED, creator=self.creator, join_emoji=join_emoji),
            embed=embed(),
        )
        await prompt.add_reaction(join_emoji)
        await prompt.add_reaction(abort_emoji)

        def reaction_check(reaction, user):
            return reaction.message.id == prompt.id and not user.bot

        while True:
            reaction, user = await self.bot.wait_for(
                "reaction_add", check=reaction_check
            )

            if reaction.emoji not in (join_emoji, start_emoji, abort_emoji):
                continue

            starting = reaction.emoji == start_emoji and user == self.creator
            is_aborting = reaction.emoji == abort_emoji and user == self.creator

            if is_aborting:
                await lobby.send(
                    msg(messages.LOBBY_CANCELLED, mention=self.creator.mention)
                )
                await prompt.delete()
                return False

            if reaction.emoji == join_emoji:
                self.log.info("%r is joining the game", user)
                self.roster.add(user)
                await prompt.edit(embed=embed())

                if len(self.roster.all) >= bare_minimum:
                    # 3 is the bare minimum
                    await prompt.add_reaction(start_emoji)

            if starting:
                # time to start!

                if len(self.roster.all) < bare_minimum:
                    await lobby.send(
                        msg(
                            messages.LOBBY_CANT_FORCE_START,
                            mention=self.creator.mention,
                        )
                    )
                    continue

                await prompt.edit(content=msg(messages.LOBBY_STARTING), embed=None)

                try:
                    await prompt.clear_reactions()
                except discord.HTTPException:
                    pass

                return True

    async def _setup_game_area(self) -> None:
        """Create and prepare the game area."""
        try:
            date = datetime.datetime.utcnow().strftime("%m/%d %H:%M")
            guild = self.guild = await self.bot.create_guild(name=f"mafia {date}")
        except discord.HTTPException as err:
            raise RuntimeError("failed to create guild") from err

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
        guild = self.guild = self.bot.get_guild(guild.id)

        # rename the default category just for fun
        first_category = guild.categories[0]
        await first_category.edit(name="mafia")

        # delete voice-related stuff
        voice_category = guild.categories[1]
        await voice_category.delete()
        await guild.voice_channels[0].delete()

        # use the default text channel as the game chat
        self.all_chat = guild.text_channels[0]
        await self.all_chat.edit(name="game-chat")

        self.spectator_role = await guild.create_role(
            name="spectator", color=discord.Color.dark_grey()
        )
        self.dead_role = await guild.create_role(
            name="dead", color=discord.Color.dark_red()
        )

        await self.all_chat.edit(
            overwrites={self.dead_role: HUSH, self.spectator_role: HUSH}
        )

        self.spectator_chat = await first_category.create_text_channel(
            name="spec-chat",
            overwrites={
                guild.default_role: BLOCK,
                self.spectator_role: ALLOW,
                self.dead_role: ALLOW,
            },
        )

    async def _setup_mafia(self) -> None:
        """Set up the mafia members for this game and creates the chat channel."""
        # `self._setup_game_area` should've been called
        assert self.guild is not None

        mafia = self.roster.pick_mafia()
        self.log.debug("picked mafia: %r", mafia)

        self.mafia_chat = await self.category.create_text_channel(
            name="mafia-chat",
            overwrites={
                self.guild.default_role: BLOCK,
                self.dead_role: HUSH,
                **{mafia_member: ALLOW for mafia_member in self.roster.mafia},
            },
        )

        await self.mafia_chat.send(
            msg(
                messages.MAFIA_GREET,
                mentions=mention_set(self.roster.mafia),
                flavor=msg(messages.MAFIA_GREET_FLAVOR),
            )
        )

    async def _setup_investigator(self) -> None:
        """Set up the investigator's channel."""
        assert self.guild is not None

        gator = self.roster.pick_investigator()
        self.log.debug("picked gator: %r", gator)

        self.gator_house = await self.category.create_text_channel(
            name="gator-house",
            overwrites={
                self.guild.default_role: BLOCK,
                self.dead_role: HUSH,
                gator: ALLOW,
            },
        )

        await self.gator_house.send(
            msg(messages.INVESTIGATOR_GREET, mention=gator.mention)
        )

    async def _gator_nighttime(self) -> None:
        assert self.gator_house is not None
        assert self.roster.investigator is not None

        gator = self.roster.investigator

        if self.roster.is_dead(gator):
            # gator dead, no gator nighttime task 4 them!
            return

        others = self.roster.alive - {gator}

        await self.gator_house.send(
            msg(
                messages.INVESTIGATOR_VISIT_PROMPT,
                mention=gator.mention,
                players=user_listing(others),
            )
        )

        async for message in self._messages_in(self.gator_house, by=gator):
            target_name = basic_command("!visit", message.content)

            if not target_name:
                continue

            target = select_member(target_name, others)

            if not target:
                await self.gator_house.send(
                    f"{self.bot.tick(False)} {message.author.mention}: Unknown townie."
                )
                continue

            self.gator_visiting = target

            picked_message = msg(
                messages.INVESTIGATOR_PICK, mention=gator.mention, player=target,
            )
            await self.gator_house.send(picked_message)

    async def _mafia_nighttime(self) -> None:
        """Wait for the mafia to choose their victim."""
        assert self.mafia_chat is not None

        await self.mafia_chat.send(
            msg(
                messages.MAFIA_KILL_PROMPT,
                mentions=mention_set(self.roster.mafia),
                victims=user_listing(self.roster.alive_townies),
            )
        )

        async for message in self._messages_in(self.mafia_chat, by=self.roster.mafia):
            target_name = basic_command("!kill", message.content)

            if not target_name:
                continue

            target = select_member(target_name, self.roster.alive_townies)

            if not target:
                await self.mafia_chat.send(
                    f"{self.bot.tick(False)} {message.author.mention}: Unknown victim."
                )
                continue

            self.victim_tonight = target

            picked_message = msg(messages.MAFIA_PICK_VICTIM, victim=target)
            picked_message = f"{mention_set(self.roster.alive_mafia)}: {picked_message}"

            if self.victim_tonight is not None:
                # mafia is changing their mind
                changed_your_mind = msg(messages.MAFIA_PICK_VICTIM_AGAIN)
                await self.mafia_chat.send(f"{changed_your_mind} {picked_message}")
            else:
                await self.mafia_chat.send(picked_message)

    async def _nighttime(self) -> None:
        assert self.all_chat is not None
        assert self.mafia_chat is not None
        assert self.gator_house is not None
        assert self.roster.investigator is not None

        await self.all_chat.send(msg(messages.NIGHT_ANNOUNCEMENT))
        await self._lock()

        nighttime_tasks = [
            self.bot.loop.create_task(self._mafia_nighttime()),
            self.bot.loop.create_task(self._gator_nighttime()),
        ]

        await asyncio.sleep(2 if self.DEBUG else 36)

        for task in nighttime_tasks:
            task.cancel()

        # now to carry out what decisions were made during the night...

        if self.gator_visiting is not None:
            suspicious = self.gator_visiting in self.roster.mafia
            if random.randint(0, 9) == 0:
                # fail randomly
                suspicious = not suspicious
            message = (
                messages.INVESTIGATOR_RESULT_SUSPICIOUS
                if suspicious
                else messages.INVESTIGATOR_RESULT_CLEAN
            )
            await self.gator_house.send(
                msg(message, mention=self.roster.investigator.mention)
            )
            self.gator_visiting = None
        if self.victim_tonight is not None:
            await self._kill(self.victim_tonight)
            # the value is cleared tomorrow morning

        await asyncio.sleep(3)
        await self._unlock()

    async def alltalk(self):
        """Allow all game participants to speak in the main game channel."""
        for member in self.roster.all:
            self.log.debug("alltalk: allowing %r to speak in %r", member, self.all_chat)
            await self.all_chat.set_permissions(self.dead_role, **NEUTRAL_HUSH_PERMS)
            await self.all_chat.set_permissions(
                self.spectator_role, **NEUTRAL_HUSH_PERMS
            )

    async def _notify_roles(self) -> None:
        """Notify the townies of their role in the game."""
        assert self.all_chat is not None

        for player in self.roster.townies:
            if player != self.roster.investigator:
                continue
            await player.send(
                msg(messages.YOU_ARE_INNOCENT, all_chat=self.all_chat.mention)
            )

    async def _gather_hanging_votes(self) -> None:
        assert self.all_chat is not None

        def check(message: discord.Message) -> bool:
            return message.channel == self.all_chat and self.roster.is_alive(
                message.author
            )

        # TODO: these are bad
        def has_voted(voter):
            for target_id, voter_ids in self.hanging_votes.items():
                if voter.id in voter_ids:
                    return True
            return False

        def get_vote(voter):
            for target_id, voter_ids in self.hanging_votes.items():
                if voter.id in voter_ids:
                    return target_id

        while True:
            message = await self.bot.wait_for("message", check=check)
            selector = basic_command("!vote", message.content)

            if not selector:
                continue

            target = select_member(selector, self.roster.alive)

            if not target or target == message.author:
                await message.add_reaction(self.bot.emoji("generic.no"))
                continue

            self.log.debug("%s is voting to hang %s", message.author, target)

            if has_voted(message.author):
                previous_target = get_vote(message.author)

                if previous_target == target.id:
                    # voter has already voted for this person
                    await self.all_chat.send(
                        msg(
                            messages.ALREADY_VOTED_FOR,
                            voter=message.author.mention,
                            target=target,
                        )
                    )
                    continue

                # remove the vote for the other person (switching votes!)
                self.hanging_votes[previous_target].remove(message.author.id)

            self.hanging_votes[target.id].append(message.author.id)

            voted = msg(messages.VOTED_FOR, voter=message.author, target=target)
            voted += "\n\n"
            voted += "\n".join(
                msg(messages.VOTES_ENTRY, mention=f"<@{key}>", votes=len(value))
                for key, value in self.hanging_votes.items()
                if value
            )

            await self.all_chat.send(voted)

    async def _lock(self) -> None:
        """Prevent anyone from sending messages in the game channel."""
        assert self.all_chat is not None
        assert self.guild is not None
        await self.all_chat.set_permissions(self.guild.default_role, **HUSH_PERMS)

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

        header_msg: str
        listing_msg: str

        if mafia_won:
            header_msg = messages.MAFIA_WIN
            listing_msg = messages.CURRENTLY_ALIVE_MAFIA
        else:
            header_msg = messages.TOWNIES_WIN
            listing_msg = messages.CURRENTLY_ALIVE_TOWNIES

        await self.all_chat.send(
            msg(header_msg)
            + "\n\n"
            + msg(listing_msg, users=user_listing(self.roster.alive_mafia))
        )
        await self.all_chat.send(msg(messages.THANK_YOU))

        await asyncio.sleep(2.0)
        await self.alltalk()
        await asyncio.sleep(10.0)

    def _tally_up_votes(self, votes_required: int) -> Optional[Tuple[int, int]]:
        vote_tallies: Dict[int, int] = {
            target_id: len(votes) for target_id, votes in self.hanging_votes.items()
        }

        vote_board = collections.OrderedDict(
            item
            for item in sorted(
                vote_tallies.items(), key=lambda item: item[1], reverse=True,
            )
            if item[1] >= votes_required
        )

        if len(vote_board) > 1 and len(set(vote_tallies.values())) == 1:
            # all votes were above the required threshold but were the same, tied!
            return None

        if vote_board:
            return list(vote_board.items())[0]
        else:
            return None

    async def _hang_with_last_words(self, target: discord.User) -> None:
        """Let someone have their last words without anyone else talking."""
        assert self.all_chat is not None

        await self._lock()
        await self.all_chat.set_permissions(target, send_messages=True)
        await self.all_chat.send(
            f"\N{SKULL} {target.mention}, you have been voted to be hanged. "
            "Do you have any last words? You have 15 seconds."
        )
        await asyncio.sleep(3.0 if self.DEBUG else 15.0)
        await self.all_chat.set_permissions(target, overwrite=None)
        await self._kill(target)
        await self._unlock()
        await self.all_chat.send(
            f"\N{SKULL} **Rest in peace, {target}. You will be missed.** \N{SKULL}"
        )

    def _get_role_str(self, target: discord.Member) -> str:
        if target == self.roster.investigator:
            return "investigator"
        elif target in self.roster.mafia:
            return "mafia"
        else:
            return "innocent"

    async def _kill(self, target: discord.Member) -> None:
        assert self.mafia_chat is not None
        assert self.all_chat is not None

        self.log.info("killing %s (%d)", target, target.id)

        # add to dead id set in roster
        self.roster.kill(target)

        # prevent speaking/reacting in mafia channel, if they are mafia
        if target in self.roster.mafia:
            await self.mafia_chat.set_permissions(
                target, read_messages=True, **HUSH_PERMS
            )

        # prevent speaking/reacting by using dead role
        await target.add_roles(self.dead_role)

        try:
            await target.edit(nick=f"{target.name} (dead)")
        except discord.HTTPException:
            pass

    async def _daytime(self) -> None:
        assert self.all_chat is not None

        if self.victim_tonight:
            # they already died the night before; reset!
            role = self._get_role_str(self.victim_tonight)
            await self.all_chat.send(
                msg(messages.FOUND_DEAD, victim=self.victim_tonight)
            )
            self.victim_tonight = None
            await asyncio.sleep(3.0)
            await self.all_chat.send(msg(messages.THEY_ROLE, role=role))
            await asyncio.sleep(5.0)

            # if all townies are dead now, end the game
            if self.roster.all_townies_dead():
                await self._game_over(mafia_won=True)
                raise EndGame()

        # time to discuss!
        votes_required = math.floor(len(self.roster.alive) / 3)
        self.log.info(msg(messages.DISCUSSION_TIME_ANNOUNCEMENT, votes=votes_required))
        await self.all_chat.send(
            msg(
                messages.DISCUSSION_TIME_TUTORIAL,
                votes=votes_required,
                players=user_listing(self.roster.alive),
            )
        )

        # gather hanging votes.
        task = self.bot.loop.create_task(self._gather_hanging_votes())
        await asyncio.sleep(50.0)
        await self.all_chat.send(msg(messages.VOTING_TIME_REMAINING, seconds=10))
        await asyncio.sleep(5.0)
        await self.all_chat.send(msg(messages.VOTING_TIME_REMAINING, seconds=5))
        await asyncio.sleep(5.0)
        task.cancel()

        voted = self._tally_up_votes(votes_required)
        self.log.info("voted: %r", voted)

        if not voted:
            await self.all_chat.send("A verdict was not reached in time. Oh well!")
        else:
            voted_id, voted_votes = voted

            hanged = discord.utils.get(self.roster.alive, id=voted_id)
            assert hanged is not None

            # goodbye
            await self._hang_with_last_words(hanged)

            await asyncio.sleep(3)

            # reveal role
            await self.all_chat.send(
                msg(messages.WAS_ROLE, died=hanged, role=self._get_role_str(hanged))
            )

            await asyncio.sleep(5)

        # reset hanging votes
        self.hanging_votes = collections.defaultdict(list)

    async def _game_loop(self) -> None:
        assert self.all_chat is not None
        assert self.mafia_chat is not None

        # hello, everybody!
        await self.all_chat.send(
            msg(messages.GAME_START, mentions=mention_set(self.roster.all))
        )
        await asyncio.sleep(5.0)

        while True:
            # send current day/daytime state to players
            await self.all_chat.send(
                messages.DAY_ANNOUNCEMENT.format(
                    emoji=(
                        messages.DAY_EMOJI if self.daytime else messages.NIGHT_EMOJI
                    ),
                    time_of_day=(messages.DAY if self.daytime else messages.NIGHT),
                    day=self.day,
                )
            )

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

            if self.roster.all_mafia_dead():
                await self._game_over(mafia_won=False)
                break
            elif self.roster.all_townies_dead():
                await self._game_over(mafia_won=True)
                break

            if not self.daytime:
                # it's night, so move onto next
                self.day += 1
                self.daytime = True
            else:
                # it's day, so move onto night
                self.daytime = False

    async def _send_invite_to_lobby(self) -> None:
        assert self.all_chat is not None

    async def _update_filling_message(self) -> None:
        assert self.guild is not None
        assert self.all_chat is not None

        not_joined = self.roster.all - set(self.guild.members)
        text = msg(messages.FILLING_PROGRESS, waiting_on=user_listing(not_joined))

        if self._filling_message is None:
            self._filling_message = await self.all_chat.send(text)
        else:
            await self._filling_message.edit(content=text)

    async def start(self) -> None:
        """Gather participants and start the game."""
        self.log.info("game starting...")

        success = await self._gather_players()
        if success is False:
            self.log.info("hmm. game was aborted!")
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

        invite = await self.all_chat.create_invite()
        await self.lobby_channel.send(
            content=msg(
                messages.LOBBY_INVITE,
                mentions=mention_set(self.roster.all),
                invite=invite,
            )
        )

        # wait for everyone to join the server
        self.state = MafiaGameState.FILLING
        self._attach_listeners()
        await self._send_invite_to_lobby()
        await self._lock()  # lock util everyone has joined
        await self._update_filling_message()
        await self._players_joined_event.wait()
        assert self._filling_message is not None
        await self._filling_message.delete()
        await self.roster.localize()
        assert all(player.guild == self.guild for player in self.roster.all)
        await self._unlock()

        await self._setup_mafia()
        await self._setup_investigator()
        await self._notify_roles()
        await asyncio.sleep(5.0)

        self.state = MafiaGameState.STARTED
        self._game_loop_task = asyncio.create_task(self._game_loop())

        try:
            await self._game_loop_task
        except asyncio.CancelledError:
            self.log.info("game was cancelled, proceeding as normal")
        except Exception as err:
            self.log.exception("error during main game loop")
            await self.all_chat.send(msg(messages.SOMETHING_BROKE, error=err))

        await self._goodbye()

    async def _goodbye(self) -> None:
        assert self.guild is not None
        assert self.all_chat is not None

        await self.all_chat.send(msg(messages.GOODBYE, seconds=15))
        await asyncio.sleep(15.0)

        # bye bye
        self._detach_listeners()
        await self.guild.delete()
