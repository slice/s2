"""Mafia roster."""

__all__ = ["Roster"]

import math
import random
from typing import Optional, Set

from discord import Member


class Roster:
    """A class that deals with the sets of players currently in the game."""

    def __init__(self, game, *, creator) -> None:
        self.game = game

        #: The set of all players who have joined the game.
        self.all: Set[Member] = {creator}

        #: The set of all mafia members, regardless of living state.
        self.mafia: Set[Member] = set()

        #: The investigator, a player who can inspect other players for their
        #: suspiciousness. They will able to discern who is innocent and who isn't,
        #: which a slim chance of failure.
        self.investigator: Optional[Member] = None

        #: The set of all dead players' IDs.
        self.dead: Set[int] = set()

    async def localize(self) -> None:
        """Localize all player objects to the game guild."""
        get_member = self.game.guild.get_member
        self.all = {get_member(user.id) for user in self.all}
        self.mafia = {get_member(user.id) for user in self.mafia}

    def _filter_player_set(
        self, player_set: Set[Member], alive: bool = True
    ) -> Set[Member]:
        if alive:
            return {player for player in player_set if player.id not in self.dead}
        else:
            return {player for player in player_set if player.id in self.dead}

    @property
    def alive(self) -> Set[Member]:
        """Return the set of alive players."""
        return self._filter_player_set(self.all, alive=True)

    @property
    def townies(self) -> Set[Member]:
        """Return the set of all townies."""
        return self.all - self.mafia

    @property
    def alive_townies(self) -> Set[Member]:
        """Return the set of all currently alive townies."""
        return self._filter_player_set(self.townies, alive=True)

    @property
    def alive_mafia(self) -> Set[Member]:
        """Return the set of all currently alive mafia."""
        return self._filter_player_set(self.mafia, alive=True)

    def all_mafia_dead(self) -> bool:
        """Return whether all mafia are dead."""
        return self.alive_mafia == set()

    def all_townies_dead(self) -> bool:
        """Return whether all townies are dead."""
        return self.alive_townies == set()

    def pick_mafia(self, *, portion: int = 3, max: int = 2) -> Set[Member]:
        """Randomly determine the members of the mafia."""
        n_mafia = min(math.ceil(len(self.all) / portion), max)
        mafia = self.mafia = set(random.sample(self.all, n_mafia))
        return mafia

    def pick_investigator(self) -> Member:
        """Pick the investigator."""
        gator = self.investigator = random.choice(list(self.townies))
        return gator

    def is_alive(self, player: Member) -> bool:
        """Return whether a player is alive."""
        return player.id not in self.dead

    def is_dead(self, player: Member) -> bool:
        """Return whether a player is dead."""
        return not self.is_alive(player)

    def kill(self, player: Member) -> None:
        """Kill a player, removing them from the list of alive players.

        The player will still remain in the "all" set.
        """
        self.dead.add(player.id)

    def add(self, player: Member) -> None:
        """Add a player to the list of players."""
        self.all.add(player)
