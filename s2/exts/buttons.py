import datetime

import lifesaver
from lifesaver.utils.formatting import human_delta

NEXT_RELEASE = datetime.datetime(2020, 10, 5, tzinfo=datetime.timezone.utc)


class Buttons(lifesaver.Cog):
    @lifesaver.command(name="3.9", aliases=["39"])
    async def python_39_when(self, ctx):
        """python 3.9 when"""
        delta = NEXT_RELEASE - datetime.datetime.now(datetime.timezone.utc)
        await ctx.send(human_delta(delta))


def setup(bot):
    bot.add_cog(Buttons(bot))
