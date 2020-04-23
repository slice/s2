import discord
from discord.ext import commands

import lifesaver

from .game import MafiaGame


class Mafia(lifesaver.Cog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sessions = {}

    @lifesaver.command(hidden=True)
    @commands.guild_only()
    async def mafia(self, ctx: lifesaver.Context):
        """Starts a game of mafia"""
        if ctx.channel.id in self.sessions:
            await ctx.send("A game has already been started here...!")
            return

        channel_id = ctx.channel.id
        game = MafiaGame(ctx.bot, creator=ctx.author, lobby_channel=ctx.channel)
        self.sessions[channel_id] = game
        try:
            await game.start()
        except Exception as err:
            await ctx.send(f"mafia machine broke: `{err}`")
            self.log.exception("oops")
        finally:
            del self.sessions[channel_id]


def setup(bot):
    bot.add_cog(Mafia(bot))
