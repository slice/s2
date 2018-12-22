import asyncio
import datetime
import logging
from collections import defaultdict

import discord
from discord.ext import commands
from lifesaver.bot import Cog, group
from lifesaver.utils import human_delta, Table, codeblock

log = logging.getLogger(__name__)

GAME_INFO = """A message sent directly after a build notification is a **GET.**
(GETs are only counted when they are in the same channel as the build notification.)

To see your total amount of GETs and other information about yourself, type `{prefix}gets profile`.
You can also use this command to view other people's profiles.
"""


def get_channel(ctx):
    return ctx.channel.id in ctx.cog.channels


class Gets(Cog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pending_gets = defaultdict(list)
        self.locks = defaultdict(asyncio.Lock)

    @property
    def channels(self):
        return self.bot.config.gets['channels']

    @property
    def webhooks(self):
        return self.bot.config.gets['webhooks']

    @property
    def debug_mode(self):
        return self.bot.config.gets.get('debug', False)

    async def get_account(self, user: discord.User):
        async with self.bot.db.execute("""
            SELECT * FROM voyager_stats
            WHERE user_id = ?
        """, [user.id]) as cur:
            result = await cur.fetchone()
            return result

    async def create_account(self, user: discord.User):
        """Create an account for a Discord user."""
        await self.bot.db.execute("""
            INSERT INTO voyager_stats (user_id, total_gets, rank)
            VALUES (?, 0, 0)
        """, [user.id])

    async def commit_get(self, msg: discord.Message):
        log.debug('committing get for %s', msg)

        account = await self.get_account(msg.author)
        if account is None:
            # automatically create an account
            await self.create_account(msg.author)
            account = await self.get_account(msg.author)

        get_messages = self.pending_gets[msg.guild.id]
        earned = len(get_messages)

        await self.bot.db.execute("""
            UPDATE voyager_stats
            SET total_gets = total_gets + ?, last_get = ?
            WHERE user_id = ?
        """, [earned, datetime.datetime.utcnow(), msg.author.id])

        await self.bot.db.execute("""
            INSERT INTO voyager_gets (user_id, get_message_id, voyager_message_id, channel_id, guild_id)
            VALUES (?, ?, ?, ?, ?)
        """, [msg.author.id, msg.id, get_messages[-1].id, msg.channel.id, msg.guild.id])

        now_gets = account[1] + earned

        if earned > 1:
            await msg.channel.send(f'{now_gets} (+{earned})')
        else:
            await msg.channel.send(now_gets)

        await self.bot.db.commit()

        log.debug('committed get for %s', msg)

    async def on_message(self, msg):
        if msg.webhook_id in self.webhooks:
            self.pending_gets[msg.guild.id].append(msg)
            return

        if msg.channel.id not in self.channels:
            return

        async with self.locks[msg.guild.id]:
            if msg.author.bot or msg.guild.id not in self.pending_gets:
                return

            await self.commit_get(msg)
            del self.pending_gets[msg.guild.id]

    @group()
    @commands.check(get_channel)
    async def gets(self, ctx):
        """༼ つ ◕_◕ ༽つ TAKE MY GETS ༼ つ ◕_◕ ༽つ"""

    @gets.command()
    async def top(self, ctx):
        """Shows the top GETters"""
        table = Table('User', 'GETs')

        async with ctx.bot.db.execute("""
            SELECT * FROM voyager_stats
            ORDER BY total_gets DESC
            LIMIT 10
        """) as cur:
            async for row in cur:
                user = ctx.bot.get_user(row[0])
                if not user:
                    user = '???'
                table.add_row(str(user), str(row[1]))

        await ctx.send(codeblock(await table.render(ctx.bot.loop)))

    @gets.command(aliases=['stats', 'info'])
    async def profile(self, ctx, target: discord.Member = None):
        """Shows your game profile"""
        target = target or ctx.author
        account = await self.get_account(target)

        if account is None:
            subject = "You haven't" if target == ctx.author else f"{target} hasn't"
            await ctx.send(f"{ctx.tick(False)} {subject} collected any GETs yet.")
            return

        embed = discord.Embed(title=str(target))
        last_ago = human_delta(account[3])
        embed.add_field(name='Total GETs', value=str(account[1]))
        embed.add_field(name='Last GET', value=f'{last_ago} ago')
        await ctx.send(embed=embed)

    @gets.command(hidden=True)
    @commands.is_owner()
    async def write(self, ctx, target: discord.Member, amount: int):
        """Writes the amount of GETs for a user"""
        await self.bot.db.execute("""
            UPDATE voyager_stats
            SET total_gets = ?
            WHERE user_id = ?
        """, [amount, target.id])
        await self.bot.db.commit()
        await ctx.ok()

    @gets.command(hidden=True)
    @commands.is_owner()
    async def sink(self, ctx, target: discord.Member):
        """Deletes all of a user's GETs"""
        await self.bot.db.execute("""
            UPDATE voyager_stats
            SET total_gets = 0
            WHERE user_id = ?
        """, [target.id])
        await self.bot.db.commit()
        await ctx.ok()

    @gets.command(aliases=['what'])
    async def wtf(self, ctx):
        """Shows game info"""
        await ctx.send(GAME_INFO.format(prefix=ctx.prefix))


def setup(bot):
    bot.add_cog(Gets(bot))
