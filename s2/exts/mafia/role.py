"""Mafia game roles."""

__all__ = [
    "Role",
    "RoleActionContext",
    "Mafia",
    "Doctor",
    "Escort",
    "Investigator",
    "Medium",
]

import abc
import functools
import math
from typing import Generic, Any, TypeVar, Optional, Set, TYPE_CHECKING

import discord

from . import messages
from .roster import Roster
from .formatting import user_listing, msg
from .utils import select_player, basic_command

if TYPE_CHECKING:
    from .player import Player
    from .game import MafiaGame

S = TypeVar("S")


class RoleActionContext:
    def __init__(self, **kwargs) -> None:
        self.game: "MafiaGame" = kwargs.pop("game")
        self.player: "Player" = kwargs.pop("player")
        self.message: Optional[discord.Message] = kwargs.get("message")

    async def send(self, *args, **kwargs) -> discord.Message:
        """Send a message to the channel."""
        return await self.channel.send(*args, **kwargs)

    async def reply(self, content: str) -> discord.Message:
        """Reply to the message."""
        mention = "@everyone" if self.player is None else self.player.mention
        return await self.send(f"{mention}: {content}")

    @property
    def group_channel(self) -> discord.TextChannel:
        """Return the channel for this grouped role."""
        assert self.player.role.grouped
        return self.game.role_chats[self.player.role]

    @property
    def channel(self) -> discord.TextChannel:
        """Return the channel that this role action is taking place in."""
        assert self.player.channel is not None
        return self.player.channel

    @property
    def guild(self) -> Optional[discord.Guild]:
        """Return the guild that the message was sent in."""
        if self.message is None:
            return None
        assert (guild := self.message.guild) is not None
        return guild

    @property
    def roster(self) -> Roster:
        """Return the game roster."""
        assert (roster := self.game.roster) is not None
        return roster

    async def select_command(
        self, command: str, players: Set["Player"]
    ) -> Optional["Player"]:
        assert self.message is not None

        target_name = basic_command(command, self.message.content)

        if target_name is None:
            return None

        target = select_player(target_name, players)

        if target is None:
            await self.message.add_reaction(self.game.bot.tick(False))
            return None

        return target


class Role(abc.ABC, Generic[S]):
    """A role that a player can play in the game."""

    #: The name of this role.
    name: str

    #: Whether at least one person with this role should be present in every game.
    guaranteed: bool = False

    #: Whether people in this role should have their own channel together.
    grouped: bool = False

    #: Whether people in this role are considered "evil" or not. Typically, those
    #: who would side with the mafia would be considered "evil", including the
    #: mafia themselves.
    evil: bool = False

    #: The state key to use for this role.
    state_key: Optional[str] = None

    @classmethod
    def grouped_chat(cls, game: "MafiaGame") -> Optional[discord.TextChannel]:
        """Return the grouped chat for this role."""
        assert cls.grouped
        return game.role_chats.get(cls)

    @classmethod
    async def on_message(
        cls, ctx: RoleActionContext, state: Optional[S]
    ) -> Optional[S]:
        """Handle messages sent in the player's personal channel."""

    @classmethod
    async def on_night_begin(cls, ctx: RoleActionContext) -> None:
        """Handle the night's beginning."""

    @classmethod
    async def on_night_end(cls, ctx: RoleActionContext, state: Optional[S]) -> None:
        """Handle the night's end."""

    @classmethod
    def n_players(cls, roster: Roster) -> int:
        """Return the amount of players who should have this role."""
        return 1

    @staticmethod
    def listener(*, priority: int = 0):
        def decorator(func):
            @functools.wraps(func)
            async def _handler(*args, **kwargs):
                return await func(*args, **kwargs)

            _handler._listener_priority = priority
            return classmethod(_handler)

        return decorator


class Innocent(Role):
    """The ordinary people of the town.

    This role is special in that any amount of players can have it, and that
    players receive this role by default.
    """

    name = "Innocent"
    guaranteed = True


class Mafia(Role):
    """The murderers of the town."""

    name = "Mafia"
    grouped = True
    evil = True
    guaranteed = True

    @classmethod
    def n_players(cls, roster: Roster) -> int:
        """Calculate how much mafia there should be in a game."""
        return min(math.floor(len(roster.players) / 3), 3)

    state_key = "mafia_victim"

    @Role.listener()
    async def on_message(
        cls, ctx: RoleActionContext, state: Optional["Player"]
    ) -> Optional["Player"]:
        target = await ctx.select_command("!kill", ctx.roster.alive_townies)
        if target is None:
            return state
        await ctx.group_channel.send(
            "@everyone: " + msg(messages.MAFIA_PICK, victim=target)
        )
        return target

    @Role.listener()
    async def on_night_begin(cls, ctx: RoleActionContext) -> None:
        assert ctx.roster is not None
        await ctx.group_channel.send(
            "@everyone: "
            + msg(
                messages.ACTION_PROMPTS["Mafia"],
                victims=user_listing(ctx.roster.alive_townies),
            )
        )

    @Role.listener()
    async def on_night_end(
        cls, ctx: RoleActionContext, victim: Optional["Player"]
    ) -> None:
        if victim is not None:
            await victim.kill()
            await ctx.group_channel.send(
                "@everyone: " + msg(messages.MAFIA_SUCCESS, victim=victim)
            )


class Doctor(Role):
    """Able to prevent someone from dying if they are attacked."""

    name = "Doctor"


class Escort(Role):
    """Able to block someone from doing something."""

    name = "Escort"


class Investigator(Role):
    """Able to investigate someone for suspiciousness."""

    name = "Investigator"

    state_key = "investigator_target"

    @classmethod
    def _targets(cls, ctx: RoleActionContext) -> Set["Player"]:
        return ctx.roster.alive - {ctx.player}

    @Role.listener()
    async def on_message(
        cls, ctx: RoleActionContext, state: Optional["Player"]
    ) -> Optional["Player"]:
        target = await ctx.select_command("!visit", cls._targets(ctx))
        if target is None:
            return state
        await ctx.reply(msg(messages.INVESTIGATOR_PICK, player=target))
        return target

    @Role.listener()
    async def on_night_begin(cls, ctx: RoleActionContext) -> None:
        assert ctx.roster is not None

        await ctx.send(
            msg(
                messages.ACTION_PROMPTS["Investigator"],
                players=user_listing(cls._targets(ctx)),
            )
        )

    @Role.listener()
    async def on_night_end(
        cls, ctx: RoleActionContext, target: Optional["Player"]
    ) -> None:
        if target is None:
            return

        message = (
            messages.INVESTIGATOR_RESULT_SUSPICIOUS
            if target.mafia
            else messages.INVESTIGATOR_RESULT_CLEAN
        )

        await ctx.reply(msg(message))


class Medium(Role):
    """Able to speak to the dead once a game."""

    name = "Medium"
