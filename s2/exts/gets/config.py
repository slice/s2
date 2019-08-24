__all__ = ["GetsConfig"]

import typing as T

import lifesaver


class GetsConfig(lifesaver.config.Config):
    webhooks: T.List[int]
    channels: T.List[int]
    debug: bool
