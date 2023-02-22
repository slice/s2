"""Mafia roster."""

__all__ = ["Roster"]

import random
from typing import Callable, Set, Union, Optional, TYPE_CHECKING

import discord

from . import role
from .utils import UserLike

if TYPE_CHECKING:
    from .player import Player
    from .role import AnyRoleType
    from .game import MafiaGame


class Roster:
    """A class that deals with the set of players currently in the game."""

    def __init__(self, game: "MafiaGame", players: Set["Player"]) -> None:
        self.game = game

        #: The set of all players.
        self.players = players

    def get_player(self, member: Union[int, UserLike]) -> Optional["Player"]:
        """Get a player from a member."""
        return discord.utils.find(
            lambda player: player.id == member or player.member == member, self.players
        )

    def sample(self, n: int) -> Set["Player"]:
        """Return a random sample of players."""
        return set(random.sample(self.players, n))

    async def localize(self) -> None:
        """Localize all players to the game guild."""
        assert self.game.guild is not None
        for player in self.players:
            localized_member = self.game.guild.get_member(player.member.id)
            assert localized_member is not None
            player.member = localized_member

    def _filter_players(
        self,
        predicate: Callable[["Player"], bool],
        players: Optional[Set["Player"]] = None,
    ) -> Set["Player"]:
        players = players or self.players
        return set(filter(predicate, players))

    def with_role(self, role: "AnyRoleType") -> Set["Player"]:
        """Return the set of players with a role."""
        return self._filter_players(lambda player: player.role is role)

    @property
    def alive(self) -> Set["Player"]:
        """Return the set of alive players."""
        return self._filter_players(lambda player: player.alive)

    @property
    def nocturnal(self) -> Set["Player"]:
        """Return the set of "active" players (those who are active at night)."""
        return self._filter_players(lambda player: player.role is not role.Innocent)

    @property
    def dead(self) -> Set["Player"]:
        """Return the set of dead players."""
        return self._filter_players(lambda player: player.dead)

    @property
    def mafia(self) -> Set["Player"]:
        """Return the set of all mafia."""
        return self._filter_players(lambda player: player.mafia)

    @property
    def alive_mafia(self) -> Set["Player"]:
        """Return the set of all currently alive mafia."""
        return self._filter_players(lambda player: player.alive, self.mafia)

    @property
    def townies(self) -> Set["Player"]:
        """Return the set of all townies."""
        return self.players - self.mafia

    @property
    def alive_townies(self) -> Set["Player"]:
        """Return the set of all currently alive townies."""
        return self._filter_players(lambda player: player.alive, self.townies)

    def all_mafia_dead(self) -> bool:
        """Return whether all mafia are dead."""
        return self.alive_mafia == set()

    def all_townies_dead(self) -> bool:
        """Return whether all townies are dead."""
        return self.alive_townies == set()

    def add(self, player: "Player") -> None:
        """Add a player to the set of players."""
        self.players.add(player)

    def __repr__(self) -> str:
        return f"<Roster players={self.players!r}>"
