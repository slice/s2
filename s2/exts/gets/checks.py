__all__ = ["get_channel"]

import lifesaver


def get_channel(ctx: lifesaver.Context) -> bool:
    """A check that enforces commands to only be runnable from GET channels."""
    return ctx.channel.id in ctx.cog.config.channels
