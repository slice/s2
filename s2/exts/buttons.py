import datetime

import lifesaver
from lifesaver.utils.formatting import human_delta

PY38_RELEASE = datetime.datetime(2019, 10, 21, tzinfo=datetime.timezone.utc)


class Buttons(lifesaver.Cog):
    @lifesaver.command(name='3.8', aliases=['38'])
    async def python_38_when(self, ctx):
        """python 3.8 when"""
        delta = PY38_RELEASE - datetime.datetime.now(datetime.timezone.utc)
        await ctx.send(human_delta(delta))


def setup(bot):
    bot.add_cog(Buttons(bot))
