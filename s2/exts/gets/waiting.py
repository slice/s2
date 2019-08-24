__all__ = ["wait_for_n_messages"]

import asyncio


async def wait_for_n_messages(
    bot, channel, *, messages: int, timeout: int, check=None
) -> bool:
    """Wait for a certain amount of messages to pass in a window of time.

    Returns whether the number of messages was reached.
    """

    def default_check(msg):
        return msg.channel == channel

    async def message_counter():
        amount = 0

        while True:
            await bot.wait_for("message", check=check or default_check)
            amount += 1

            if amount >= messages:
                return

    try:
        await asyncio.wait_for(message_counter(), timeout=timeout, loop=bot.loop)
    except asyncio.TimeoutError:
        return False

    return True
