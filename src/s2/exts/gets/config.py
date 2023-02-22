__all__ = ["GetsConfig"]

import lifesaver.config


class GetsConfig(lifesaver.config.Config):
    webhooks: list[int]
    get_channels: list[int]
    allowed_guilds: list[int]
    debug: bool
