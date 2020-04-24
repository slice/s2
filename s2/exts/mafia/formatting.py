__all__ = ["user_listing", "msg"]

import random
from typing import Union, List, Iterable, TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from .player import Player
    from .utils import UserLikeIterable


def user_listing(users: Union["UserLikeIterable", Iterable["Player"]]) -> str:
    """Format a list of users."""
    return "\n".join(f"\N{EM DASH} {user}" for user in users)


def msg(message: Union[str, List[str]], *args, **kwargs) -> str:
    """Process a message, randomly choosing from it if it's a ``list``."""
    if isinstance(message, list):
        message = random.choice(message)
    return message.format(*args, **kwargs)


def mention_set(entities: Union["UserLikeIterable", Iterable["Player"]]) -> str:
    """Format a list of mentions from a list of users."""

    def mention(entity: Union[discord.User, discord.Member, "Player"]) -> str:
        if isinstance(entity, (discord.User, discord.Member)):
            return entity.mention
        else:
            return entity.member.mention

    return ", ".join(mention(entity) for entity in entities)
