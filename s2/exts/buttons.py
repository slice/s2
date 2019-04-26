import datetime

from lifesaver.bot import Cog, command
from lifesaver.utils.formatting import human_delta

PY38_RELEASE = datetime.datetime(2019, 10, 21, tzinfo=datetime.timezone.utc)


class Buttons(Cog):
    @command(name='3.8', aliases=['38'])
    async def python_38_when(self, ctx):
        """python 3.8 when"""
        delta = PY38_RELEASE - datetime.datetime.now(datetime.timezone.utc)
        await ctx.send(human_delta(delta))


def setup(bot):
    bot.add_cog(Buttons(bot))
