import aiohttp
from discord.ext import commands
from lifesaver.bot import Cog, command
from lifesaver.utils.formatting import truncate, pluralize

HEADERS = {'User-Agent': 's2/0.0.0 (https://github.com/slice)'}
ENDPOINT = 'https://haveibeenpwned.com/api/v2/breachedaccount/{account}'


class HIBP(Cog):
    @command(typing=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def hibp(self, ctx, *, email):
        """Have you been pwned?"""
        async with aiohttp.ClientSession(headers=HEADERS) as sess:
            async with sess.get(ENDPOINT.format(account=email)) as resp:
                if resp.status == 404:
                    await ctx.send("\U00002705 not pwned")
                    return
                pwned = await resp.json()

        accounts = ', '.join(f"{site['Title']} ({site['Domain']})" for site in pwned)
        website = pluralize(website=len(pwned), with_quantity=True)
        await ctx.send(f"\U0001f62c oh no, pwned on {website}!\n\n{truncate(accounts, 1800)}")


def setup(bot):
    bot.add_cog(HIBP(bot))
