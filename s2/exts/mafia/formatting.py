__all__ = ["user_listing", "msg", "Message"]

import random
from typing import Any, Union, List, Iterable, TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from .player import Player
    from .utils import UserLikeIterable

Message = Union[str, List[str]]


def user_listing(
    users: Union["UserLikeIterable", Iterable["Player"]], *, commas: bool = False
) -> str:
    """Format a list of users."""
    if commas:
        return ", ".join(map(str, users))
    return "\n".join(f"\N{EM DASH} {user}" for user in users)


def msg(message: Message, **kwargs: Any) -> str:
    """Process a message, randomly choosing from it if it's a ``list``."""
    if isinstance(message, list):
        message = random.choice(message)
    return message.format(**kwargs)


def mention_set(entities: Union["UserLikeIterable", Iterable["Player"]]) -> str:
    """Format a list of mentions from a list of users."""

    def mention(entity: Union[discord.User, discord.Member, "Player"]) -> str:
        if isinstance(entity, (discord.User, discord.Member)):
            return entity.mention
        else:
            return entity.member.mention

    return ", ".join(mention(entity) for entity in entities)
