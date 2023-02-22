"""Mafia game roles."""

__all__ = [
    "AnyRoleType",
    "Role",
    "RoleActionContext",
    "Mafia",
    "Doctor",
    "Escort",
    "Investigator",
    "Medium",
]

import abc
import asyncio
import math
from typing import Type, Any, Callable, Generic, TypeVar, Optional, Set, TYPE_CHECKING

import discord

from . import messages
from .roster import Roster
from .formatting import user_listing, msg, Message
from .utils import select_player, basic_command
from .memory import Key

if TYPE_CHECKING:
    from .player import Player
    from .game import MafiaGame

T = TypeVar("T")
S = TypeVar("S")

AnyRoleType = Type["Role[Any]"]


class RoleActionContext:
    def __init__(
        self,
        *,
        game: "MafiaGame",
        player: "Player",
        message: Optional[discord.Message] = None,
    ) -> None:
        self.game = game
        self.player = player
        self.message = message

    async def send(
        self, content: str, *, embed: Optional[discord.Embed] = None
    ) -> discord.Message:
        """Send a message to the role channel."""
        target = self.group_channel if self.player.role.grouped else self.channel
        return await target.send(content, embed=embed)

    async def reply(self, content: str) -> discord.Message:
        """Reply to the message."""
        more_than_one = (
            self.player.role.grouped
            and len(self.roster.with_role(self.player.role)) > 1
        )
        mention = "@everyone" if more_than_one else self.player.mention
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


def _role_listener_deco(
    *, priority: int = 0
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorate a function as a role event listener."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        func._listener_priority = priority  # type: ignore[attr-defined]
        return func

    return decorator


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

    #: The memory key to use for this role.
    key: Optional[Key] = None

    @classmethod
    def localized_key(cls, player: "Player") -> Optional[Key]:
        """Compute the key, localized if necessary."""
        if (key := cls.key) is None:
            return None

        return key if player.role.grouped else key.localized(str(player.id))

    @classmethod
    def grouped_chat(cls, game: "MafiaGame") -> Optional[discord.TextChannel]:
        """Return the grouped chat for this role."""
        assert cls.grouped
        return game.role_chats.get(cls)

    @classmethod
    def n_players(cls, roster: Roster) -> int:
        """Return the amount of players who should have this role."""
        return 1

    @staticmethod
    def listener(
        *, priority: int = 0
    ) -> Callable[[Callable[..., T]], Callable[..., T]]:
        """A decorator that listens for events."""
        return _role_listener_deco(priority=priority)

    @classmethod
    @_role_listener_deco()
    async def on_message(
        cls, ctx: RoleActionContext, state: Optional[S]
    ) -> Optional[S]:
        """Handle messages sent in the player's personal channel."""

    @classmethod
    @_role_listener_deco()
    async def on_night_begin(cls, ctx: RoleActionContext, state: Optional[S]) -> None:
        """Handle the night's beginning."""

    @classmethod
    @_role_listener_deco()
    async def on_night_end(cls, ctx: RoleActionContext, state: Optional[S]) -> None:
        """Handle the night's end."""


class PickerRole(Role[Optional["Player"]]):
    """A role that non-persistently picks someone at night.

    What is done when the night ends is up to the inheriting class.
    """

    pick_command: str

    @classmethod
    def get_pick_response(cls, ctx: RoleActionContext) -> Message:
        """Return the message used when the player has picked."""
        return messages.PICK_RESPONSE[cls.name]

    @classmethod
    def get_pick_prompt(cls, ctx: RoleActionContext) -> Message:
        """Return the message used to prompt the player to pick."""
        return messages.PICK_PROMPT[cls.name]

    @classmethod
    def should_allow_picking(cls, ctx: RoleActionContext) -> bool:
        """Return whether to prompt and let the player pick."""
        return True

    @classmethod
    def get_targets(cls, ctx: RoleActionContext) -> Set["Player"]:
        """Return the set of targets that can be picked from."""
        return ctx.roster.alive - {ctx.player}

    @classmethod
    @Role.listener()
    async def on_night_begin(cls, ctx: RoleActionContext, state: None) -> None:
        if not cls.should_allow_picking(ctx):
            return

        await ctx.reply(
            msg(cls.get_pick_prompt(ctx), targets=user_listing(cls.get_targets(ctx)))
        )

    @classmethod
    @Role.listener()
    async def on_message(
        cls, ctx: RoleActionContext, state: Optional["Player"]
    ) -> Optional["Player"]:
        if not cls.should_allow_picking(ctx):
            return state

        targets = cls.get_targets(ctx)
        target = await ctx.select_command(cls.pick_command, targets)

        if target is None:
            return state

        await ctx.reply(msg(cls.get_pick_response(ctx), target=target))
        return target


class Innocent(Role[None]):
    """The ordinary people of the town.

    This role is special in that any amount of players can have it, and that
    players receive this role by default.
    """

    name = "Innocent"
    guaranteed = True


class Mafia(PickerRole):
    """The murderers of the town."""

    name = "Mafia"
    grouped = True
    evil = True
    guaranteed = True

    pick_command = "!kill"
    key = Key("mafia_victim")

    @classmethod
    def n_players(cls, roster: Roster) -> int:
        """Calculate how much mafia there should be in a game."""
        return max(min(math.floor(len(roster.players) / 3), 3), 1)

    @classmethod
    def get_targets(cls, ctx: RoleActionContext) -> Set["Player"]:
        return ctx.roster.alive_townies

    @classmethod
    @Role.listener()
    async def on_night_end(
        cls, ctx: RoleActionContext, victim: Optional["Player"]
    ) -> None:
        if victim is None:
            return

        ctx.game.memory[Key("attacked").localized(victim)] = True

        was_healed = any(
            value == victim
            for (key, value) in ctx.game.memory.items()
            if key.key.startswith("heal_target_")
        )

        if was_healed:
            await ctx.reply(msg(messages.MAFIA_FAILURE, target=victim))
            return

        await victim.kill()
        await ctx.reply(msg(messages.MAFIA_SUCCESS, target=victim))


class Doctor(PickerRole):
    """Able to prevent someone from dying if they are attacked."""

    name = "Doctor"

    pick_command = "!heal"
    key = Key("heal_target")

    # only notify the player after end events have already taken place, so we
    # know if they got attacked or not
    @classmethod
    @Role.listener(priority=-100)
    async def on_night_end(
        cls, ctx: RoleActionContext, target: Optional["Player"]
    ) -> None:
        if not target:
            return

        was_attacked = Key("attacked").localized(target) in ctx.game.memory
        if was_attacked:
            assert target.channel is not None
            await target.channel.send(
                f"{target.mention}: " + msg(messages.DOCTOR_YOU_WERE_SAVED)
            )

        message_key = "healed" if was_attacked else "noop"
        await ctx.send(msg(messages.DOCTOR_RESULT[message_key], target=target))


class Escort(PickerRole):
    """Able to block someone from doing something."""

    name = "Escort"


class Investigator(PickerRole):
    """Able to investigate someone for suspiciousness."""

    name = "Investigator"

    pick_command = "!visit"
    key = Key("investigator_target")

    @classmethod
    @Role.listener()
    async def on_night_end(
        cls, ctx: RoleActionContext, target: Optional["Player"]
    ) -> None:
        if target is None:
            return

        message = (
            messages.INVESTIGATOR_RESULT_SUSPICIOUS
            if target.suspicious
            else messages.INVESTIGATOR_RESULT_CLEAN
        )

        await ctx.reply(msg(message))


class Medium(Role[bool]):
    """Able to speak to the dead once a game."""

    name = "Medium"
    key = Key("has_seanced", persistent=True)

    seance_perms = discord.PermissionOverwrite(
        read_messages=True, read_message_history=False
    )

    @classmethod
    @Role.listener()
    async def on_message(cls, ctx: RoleActionContext, state: bool) -> bool:
        assert ctx.message is not None

        if ctx.message.content != "!seance":
            return state

        if state:
            await ctx.reply(msg(messages.MEDIUM_ALREADY_SEANCED))
            return state

        await ctx.reply(msg(messages.MEDIUM_SEANCE))

        assert (spec_chat := ctx.game.spectator_chat) is not None

        await spec_chat.set_permissions(ctx.player.member, overwrite=cls.seance_perms)
        await asyncio.sleep(1)
        await spec_chat.send(
            "@everyone: " + msg(messages.MEDIUM_SEANCE_ANNOUNCEMENT, medium=ctx.player)
        )

        return True

    @classmethod
    @Role.listener()
    async def on_night_begin(
        cls, ctx: RoleActionContext, state: Optional[bool]
    ) -> None:
        if state is True:
            # already seanced
            return

        if not ctx.roster.dead:
            # no dead
            return

        await ctx.reply(msg(messages.PICK_PROMPT["Medium"]))

    @classmethod
    @Role.listener()
    async def on_night_end(cls, ctx: RoleActionContext, state: Optional[bool]) -> None:
        assert (spec_chat := ctx.game.spectator_chat) is not None

        if ctx.player.member not in spec_chat.overwrites:
            return

        await spec_chat.set_permissions(ctx.player.member, overwrite=None)
