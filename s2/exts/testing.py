import asyncio
import random

import discord
import lifesaver
import jishaku
from discord.ext import commands


class Testing(lifesaver.Cog, command_attrs=dict(hidden=True)):
    @lifesaver.command()
    async def simple_pagination(self, ctx: lifesaver.Context):
        ctx.add_line("one")
        ctx.add_line("two")
        ctx.add_line("oatmeal")

        await ctx.paginate()

    @lifesaver.command()
    async def interfaced_pagination(self, ctx: lifesaver.Context):
        ctx.add_line("one")
        ctx.add_line("two")

        interface = await ctx.paginate(force_interface=True)

        for n in range(3):
            await interface.add_line(f"post {n}")
            await asyncio.sleep(1)


def setup(bot):
    bot.add_cog(Testing(bot))
