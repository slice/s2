from random import choice

import discord
from discord import ActivityType
from lifesaver.bot import Cog

PLAYING_STATUSES = [
    (ActivityType.watching, "you"),
    (ActivityType.listening, "rain"),
    (ActivityType.watching, "e621"),
    (ActivityType.playing, "with elixir"),
]


class Cycle(Cog):
    async def on_ready(self):
        await self.cycle()

    async def cycle(self):
        (type_, name) = choice(PLAYING_STATUSES)
        game = discord.Activity(type=type_, name=name)
        await self.bot.change_presence(status=discord.Status.dnd, activity=game)

    @Cog.every(60)
    async def cycle_playing_status(self):
        await self.cycle()


def setup(bot):
    bot.add_cog(Cycle(bot))
