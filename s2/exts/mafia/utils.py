"""Mafia utilities."""

__all__ = [
    "UserLike",
    "UserLikeSet",
    "UserLikeSeq",
    "mention_set",
    "basic_command",
    "select_member",
]

from typing import Union, Iterable, Optional, Set, TYPE_CHECKING

import discord
import fuzzywuzzy.process as fw_process

if TYPE_CHECKING:
    from .player import Player

UserLike = Union[discord.User, discord.Member]
UserLikeIterable = Iterable[UserLike]


def resolve_state_key(player: "Player") -> Optional[str]:
    """Resolve a state key for a player. If there's no state key, None is returned."""
    if (state_key := player.role.state_key) is None:
        return None

    if player.role.grouped:
        # since the player is in a grouped role, use the same state key for
        # everyone in the group
        return state_key
    else:
        return state_key + f"_{player.member.id}"


def basic_command(name: str, inp: str) -> Optional[str]:
    name = name + " "

    if not inp.startswith(name):
        return None
    return inp[len(name) :]


def select_player(selector: str, players: Set["Player"]) -> Optional["Player"]:
    direct_match = discord.utils.find(
        lambda player: str(player.member.name).lower() == selector.lower()
        or str(player.member).lower() == selector.lower()
        or str(player.member.id) == selector,
        players,
    )

    if direct_match is not None:
        return direct_match

    mapping = {player.id: player.member.name for player in players}
    _, score, selected_id = fw_process.extractOne(selector, mapping)

    if score > 50:  # arbitrary threshold
        return discord.utils.find(lambda player: player.id == selected_id, players)

    return None
