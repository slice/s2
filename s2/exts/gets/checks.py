__all__ = ["get_zone"]

import lifesaver


def get_zone_only(ctx: lifesaver.Context) -> bool:
    """
    A check that enforces commands to only be runnable from GET channels
    """
    config = ctx.cog.config
    if (guild := ctx.guild) is not None and guild.id in config.allowed_guilds:
        return True
    if ctx.channel.id in config.get_channels:
        return True
    return False
