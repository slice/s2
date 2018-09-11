import discord
from discord.ext import commands
from discord.http import Route
from lifesaver.bot import Cog, command


class Slowmode(Cog):
    @command(aliases=['sm'], typing=True)
    @commands.has_permissions(manage_roles=True)
    async def slowmode(self, ctx, time: int):
        """Applies slowmode in this channel."""
        route = Route('PATCH', '/channels/{channel_id}', channel_id=ctx.channel.id)

        if time > 120:
            await ctx.send('Maximum time is 120s.')
            return

        try:
            await ctx.bot.http.request(route, json={'rate_limit_per_user': time})
        except discord.HTTPException as err:
            await ctx.send(f'Failed to set slowmode: {err}')
        else:
            if time == 0:
                await ctx.send('Removed slowmode.')
            else:
                await ctx.send('Applied slowmode.')


def setup(bot):
    bot.add_cog(Slowmode(bot))
