__all__ = ["Player"]

from typing import Optional, Type, Any, TYPE_CHECKING

import discord

from .permissions import HUSH_PERMS
from .role import Mafia

if TYPE_CHECKING:
    from .game import MafiaGame
    from .role import Role


class Player:
    """A player in a mafia game."""

    def __init__(
        self,
        member: discord.Member,
        *,
        role: Type["Role[Any]"],
        channel: Optional[discord.TextChannel] = None,
        game: "MafiaGame",
    ) -> None:
        #: The Discord member of this player.
        self.member = member

        #: The role of this player in the game.
        self.role = role

        #: The will of this player, shown to everyone upon their death.
        self.will: Optional[str] = None

        #: Is this player alive?
        self.alive: bool = True

        #: The player's personal channel.
        self.channel = channel

        self._game = game

    @property
    def id(self) -> int:
        """Return the player's ID."""
        return self.member.id

    @property
    def mention(self) -> str:
        """Return a mention to the player."""
        return self.member.mention

    @property
    def mafia(self) -> bool:
        """Check if the player has the ``Mafia`` role."""
        return self.role is Mafia

    @property
    def dead(self) -> bool:
        """Check if the player is dead."""
        return not self.alive

    async def kill(self) -> None:
        """Kill the player."""
        self.alive = False

        if (channel := self.channel) is not None:
            embed = discord.Embed(title="You died!", color=discord.Color.red())
            await channel.send(content=self.mention, embed=embed)

        if self.mafia:
            # prevent speaking in mafia chat
            mafia_chat = self._game.role_chats[Mafia]
            overwrite = discord.PermissionOverwrite(read_messages=True, **HUSH_PERMS)
            await mafia_chat.set_permissions(self.member, overwrite=overwrite)

        # prevent speaking everywhere with dead role
        assert self._game.player_role is not None
        assert self._game.dead_role is not None
        await self.member.remove_roles(self._game.player_role)
        await self.member.add_roles(self._game.dead_role)

        try:
            await self.member.edit(nick=f"{self.member.name} (dead)")
        except discord.HTTPException:
            pass

    def __hash__(self) -> int:
        return hash(self.member)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Player):
            return NotImplemented
        return self.member == other.member

    def __repr__(self) -> str:
        return f"<Player {self.member} role={self.role!r}>"

    def __str__(self) -> str:
        return str(self.member)
