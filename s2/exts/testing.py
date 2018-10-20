from lifesaver.bot import Cog, command


class Testing(Cog):
    @command()
    async def multirest(ctx, *, a, b):
        await ctx.send(f'{a} - {b}')


def setup(bot):
    bot.add_cog(Testing(bot))
