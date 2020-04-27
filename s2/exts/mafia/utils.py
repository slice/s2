"""Mafia utilities."""

__all__ = [
    "UserLike",
    "UserLikeIterable",
    "basic_command",
    "select_player",
]

from typing import Union, Iterable, Optional, Set, TYPE_CHECKING

import discord
import fuzzywuzzy.process as fw_process

if TYPE_CHECKING:
    from .player import Player

UserLike = Union[discord.User, discord.Member]
UserLikeIterable = Iterable[UserLike]


def basic_command(name: str, input: str) -> Optional[str]:
    """Parse a basic command."""
    name += " "

    if not input.startswith(name):
        return None
    return input[len(name) :]


def select_player(selector: str, players: Set["Player"]) -> Optional["Player"]:
    """Select a player from a set of players using a selector."""
    direct_match = discord.utils.find(
        lambda player: str(player.member.name).lower() == selector.lower()
        or str(player.member).lower() == selector.lower()
        or str(player.member.id) == selector
        or player.mention == selector,
        players,
    )

    if direct_match is not None:
        return direct_match

    mapping = {player.id: player.member.name for player in players}
    selected_id: int
    _, score, selected_id = fw_process.extractOne(selector, mapping)

    if score > 50:  # arbitrary threshold
        return discord.utils.find(lambda player: player.id == selected_id, players)

    return None
