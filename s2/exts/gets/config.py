__all__ = ["GetsConfig"]

import typing as T

import lifesaver


class GetsConfig(lifesaver.config.Config):
    webhooks: T.List[int]
    get_channels: T.List[int]
    allowed_guilds: T.List[int]
    debug: bool
