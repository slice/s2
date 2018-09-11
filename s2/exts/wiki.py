import aiohttp
from lifesaver.bot import Cog, command
from discord.ext import commands


class MediaWikiSearcher:
    endpoint = None

    @classmethod
    async def search(cls, query, *, session):
        url = f"{cls.endpoint}/api.php"
        params = {
            "format": "json",
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": 3,
        }

        async with session.get(url, params=params) as resp:
            body = await resp.json()
            return body["query"]["search"]

    @classmethod
    def format_result(cls, result):
        title = result["title"]
        underscored_title = title.replace(" ", "_")
        return f"{cls.endpoint}/{underscored_title}"


class TerrariaSearch(MediaWikiSearcher):
    endpoint = "https://terraria.gamepedia.com"


class Wiki(Cog):
    @command(typing=True, aliases=["tw"])
    @commands.cooldown(1, 2, type=commands.BucketType.user)
    async def terraria(self, ctx, *, query):
        """Searches the Terraria wiki."""

        try:
            results = await TerrariaSearch.search(query, session=self.session)

            if not results:
                await ctx.send("No results.")
                return

            top_link = TerrariaSearch.format_result(results[0])

            if len(results) == 1:
                await ctx.send(top_link)

            rest = "\n".join(
                map(lambda r: "<" + TerrariaSearch.format_result(r) + ">", results[1:])
            )

            await ctx.send(f"{top_link}\n\n{rest}")
        except aiohttp.ClientError as err:
            await ctx.send(f"Failed to search: {err}")


def setup(bot):
    bot.add_cog(Wiki(bot))
