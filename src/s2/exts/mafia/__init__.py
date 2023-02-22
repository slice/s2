import fractions
from typing import (
    Coroutine,
    Callable,
    Any,
    Dict,
    Optional,
    Union,
    cast,
)

import discord
from discord.ext import commands
from discord.ext.commands._types import BotT

import lifesaver
from lifesaver.utils.formatting import Table, codeblock

from .game import MafiaGame

Listener = Callable[..., Coroutine[Any, Any, None]]


class GameConverter(commands.Converter[MafiaGame]):
    async def convert(self, ctx: commands.Context[BotT], argument: str) -> MafiaGame:
        try:
            lobby_channel_id = int(argument)
            game = cast(Mafia, ctx.bot.get_cog("Mafia")).sessions.get(lobby_channel_id)
            if game is None:
                raise commands.BadArgument(
                    f"Cannot find a Mafia game with that lobby channel ID."
                )
            return game
        except ValueError:
            raise commands.BadArgument("Lobby channel ID was not numeric.")


async def _default_mafia_game(ctx: lifesaver.Context) -> MafiaGame:
    cog = cast(Mafia, ctx.bot.get_cog("Mafia"))
    if (game := cog.get_game(ctx)) is None:
        raise commands.BadArgument("Unable to infer a Mafia game in this context.")
    return game


InferGame = commands.parameter(
    converter=GameConverter,
    default=_default_mafia_game,
    description="The Mafia game",
    displayed_default="infer the game from context",
)


class Mafia(lifesaver.Cog):
    def __init__(self, bot: lifesaver.Bot) -> None:
        super().__init__(bot)
        self.sessions: Dict[int, MafiaGame] = {}

    def get_game(
        self, ctx: Union[lifesaver.Context, discord.Guild]
    ) -> Optional[MafiaGame]:
        """Return the game according to the current context, or the game's guild."""

        if isinstance(ctx, discord.Guild):
            return discord.utils.get(self.sessions.values(), guild=ctx)

        if (game := self.sessions.get(ctx.channel.id)) is None:
            # since we're unable to fetch the game from the lobby channel, try
            # the guild that we're in
            assert ctx.guild is not None
            return self.get_game(ctx.guild)

        return game

    async def dispatch_to_game(
        self, event: str, guild: discord.Guild, *args: Any
    ) -> None:
        """Dispatch an event for a game."""

        if (game := self.get_game(guild)) is None:
            return

        event_handler = getattr(game, event)

        try:
            await event_handler(*args)
        except Exception:
            self.log.exception(
                "something went wrong while passing %s to a mafia game", event
            )

    def _passthrough_event(event: str) -> Listener:  # type: ignore[misc]
        """Generate an event handler that passes events through to mafia games.

        We determine the target game through the ``guild`` property of the first
        parameter of the handler. It is assumed that events receive an entity with such
        property.
        """

        @lifesaver.Cog.listener(event)
        async def generated_event(self: "Mafia", entity: Any, *args: Any) -> None:
            if (guild := entity.guild) is None:
                return

            await self.dispatch_to_game(event, guild, entity, *args)

        generated_event.__name__ = event

        return generated_event

    on_message = _passthrough_event("on_message")
    on_member_join = _passthrough_event("on_member_join")
    on_member_remove = _passthrough_event("on_member_remove")

    @lifesaver.group(invoke_without_command=True)
    @commands.guild_only()
    async def mafia(self, ctx: lifesaver.Context) -> None:
        """Creates a Mafia lobby

        Creates an interactive lobby for a game of Mafia, heavily inspired by
        the online game Town of Salem created by BlankMediaGames. If you are
        familiar with Town of Salem, then you'll right at home with Mafia!

        You need at least 3 players to start a game. However, 8 or more players
        are recommended or else the game won't be very fun. Try 10 or more
        players for an even better experience!

        The bot creates a server for each game, so make sure you aren't in 100
        servers or else you won't be able to join.

        In each game, the mafia and the town try to eliminate each other.
        The last group standing wins!

        The game takes place through day/night cycles. During daytime (except
        for the first day), everyone discusses a potential suspect. After
        discussion time, everyone can vote for someone who they wish to hang.

        During night, hardly anybody is asleep! At this time, the mafia can
        commit murder and townies can perform their abilities.

        ------------------------------------------------------------------------

        Each player is randomly assigned one of the following roles:

        Town: Investigator (also: "invest", "inv")

            You may visit someone every night to determine their suspiciousness.

        Town: Innocent (also: "inno")

            You are an ordinary town member.

        Mafia: Mafia

            You are a member of the mafia. Each night, you and your fellow mafia
            can decide on someone to kill. Only one target may be chosen a
            night, so make sure your collective decision wisely!

        Additional roles may be added or existing roles may be removed in the
        future, so keep your eyes peeled!.

        ------------------------------------------------------------------------

        Additional notes:

        * You can set your will, a message displayed to everyone upon the
          discovery of your death, by typing "!will" followed by a space and
          some text in your personal channel. Wills are limited to 1,000
          characters.

        * When using "!" commands that allow you to select from a list of
          players, fuzzy matching is performed. This means you can type
          usernames very loosely and the bot will likely figure out who you
          wanted to choose.
        """
        if ctx.channel.id in self.sessions:
            await ctx.send("A game has already been started here...!")
            return

        if len(ctx.bot.guilds) >= 10:
            await ctx.send("The bot is in too many servers.")
            return

        creator = cast(discord.Member, ctx.author)
        lobby_channel = cast(discord.TextChannel, ctx.channel)
        channel_id = ctx.channel.id

        game = MafiaGame(ctx.bot, creator=creator, lobby_channel=lobby_channel, ctx=ctx)
        self.sessions[channel_id] = game

        try:
            await game.start()
        except Exception as err:
            await ctx.send(f"mafia machine broke: `{err!r}`")
            self.log.exception("error during mafia")
        finally:
            del self.sessions[channel_id]

    @mafia.command(name="roles")
    async def mafia_roles(self, ctx: lifesaver.Context) -> None:
        """Shows all roles and their chances"""
        total = sum(MafiaGame.WEIGHTED_ROLES.values())

        mafia_formula = (
            "min(\N{LEFT FLOOR} n_players \N{DIVISION SIGN} 3 \N{RIGHT FLOOR}, 3)"
        )

        table = Table("Role", "Chance", "Fraction", "Weight")

        for (role, weight) in MafiaGame.WEIGHTED_ROLES.items():
            rational = weight / total
            fraction = fractions.Fraction(weight, total)
            percentage = rational * 100

            table.add_row(
                role.name,
                f"{percentage:.2f}%",
                f"{fraction.numerator}/{fraction.denominator}",
                str(weight),
            )

        roles = await table.render()

        await ctx.send(
            (
                f"The number of mafia is calculated using: `{mafia_formula}`\n"
                "Everyone has an equal chance of becoming mafia.\n\n"
                f"After the mafia has been picked, townie roles are assigned:\n\n"
                f"{codeblock(roles)}\n\n"
                f"For more information on roles, type `{ctx.prefix}help mafia`."
            )
        )

    @mafia.group(name="debug", invoke_without_command=True)
    @commands.is_owner()
    async def mafia_debug(
        self, ctx: lifesaver.Context, game: MafiaGame = InferGame
    ) -> None:
        """Reveal game state"""
        if (roster := game.roster) is None:
            await ctx.send("game hasn't started yet?")
            return

        players = "\n".join(
            f"{player}: {player.role.name}" for player in roster.players
        )

        debug_info = f"""{game.state=}

{game.lobby_channel=}
{game.creator=}

{game.role_chats=!r}
{game.memory=!r}

{players}
"""

        await ctx.send(codeblock(debug_info))

    @mafia_debug.command(name="forcejoin", aliases=["fj"], invoke_without_command=True)
    @commands.is_owner()
    async def mafia_forcejoin(
        self, ctx: lifesaver.Context, user_id: int, game: MafiaGame = InferGame
    ) -> None:
        """Forcibly adds someone to a lobby"""
        user = await ctx.bot.fetch_user(user_id)
        game.participants.add(user)
        await game._lobby_menu._update_embed()
        await ctx.send(f"{ctx.tick()} Forcibly added {user} to the lobby.")

    @mafia_debug.command(name="clean")
    @commands.is_owner()
    async def mafia_debug_clean(self, ctx: lifesaver.Context) -> None:
        """Deletes any created Mafia guilds"""
        for guild in ctx.bot.guilds:
            if "mafia " in guild.name and guild.owner == ctx.bot.user:
                await guild.delete()
        await ctx.ok()

    @mafia_debug.command(name="stop")
    @commands.is_owner()
    async def mafia_debug_stop(
        self, ctx: lifesaver.Context, game: MafiaGame = InferGame
    ) -> None:
        """Immediately ceases gameplay"""
        if (task := game._game_loop_task) is None:
            await game.game_over()
        else:
            task.cancel()
        await ctx.ok()

    @mafia_debug.command(name="admin")
    @commands.is_owner()
    async def mafia_debug_admin(
        self, ctx: lifesaver.Context, game: MafiaGame = InferGame
    ) -> None:
        """Enable administrator privileges"""
        if (guild := game.guild) is None:
            await ctx.send("Game area not found.")
            return

        permissions = discord.Permissions(administrator=True)

        role = await guild.create_role(
            name="debug admin", permissions=permissions, color=discord.Color.blue()
        )
        await cast(discord.Member, ctx.author).add_roles(role)
        await ctx.ok()

    @mafia_debug.command(name="slay")
    @commands.is_owner()
    async def mafia_debug_slay(
        self,
        ctx: lifesaver.Context,
        target: discord.Member,
        game: MafiaGame = InferGame,
    ) -> None:
        """Slays a player"""
        if (roster := game.roster) is None:
            await ctx.send("Game doesn't have a roster yet.")
            return

        if (player := roster.get_player(target)) is None:
            await ctx.send("Can't find that player.")
            return

        await player.kill()
        await ctx.ok()


async def setup(bot: lifesaver.Bot) -> None:
    await bot.add_cog(Mafia(bot))
