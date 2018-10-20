import datetime
import logging

import discord
from discord.ext import commands
from lifesaver.bot import Cog, group
from lifesaver.utils import human_delta

log = logging.getLogger(__name__)

GAME_INFO = """A message sent directly after a build notification is a **GET.**

The total amount of GETs you collect are tallied, which helps determine your **rank.**
(To see rank information, type `{prefix}gets ranks`.)

To see your total amount of GETs and other information about yourself, type `{prefix}gets profile`.
You can also use this command to view other people's profiles.

Don't ask why.
"""

RANK_COLORS = [
    discord.Color(0x45e6e5),
    discord.Color(0x457ae5),
    discord.Color(0x7a45e5),
    discord.Color(0xe545e5),
    discord.Color(0xe545b0),
    discord.Color(0xe54545),
]

RANK_INFO = """{} 0 to 9 GETs
You are a curious client modder.

{} 10 to 19 GETs
You are a young client modder.

{} 20 to 39 GETs
You are a novice client modder.

{} 40 to 59 GETs
You are an experienced client modder.

{} 60 to 79 GETs
You are a client modding aficionado.

{} 80 to \N{INFINITY} GETs
You are a Discord employee."""


def get_channel(ctx):
    return ctx.channel.id in ctx.cog.channels


def get_rank(n_gets: int) -> int:
    if 0 < n_gets < 10:
        return 0
    if 10 <= n_gets < 20:
        return 1
    elif 20 <= n_gets < 40:
        return 2
    elif 40 <= n_gets < 60:
        return 3
    elif 60 <= n_gets < 80:
        return 4
    else:
        return 5


class Gets(Cog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pending_get = None

    @property
    def channels(self):
        return self.bot.config.gets['channels']

    @property
    def webhooks(self):
        return self.bot.config.gets['webhooks']

    @property
    def debug_mode(self):
        return self.bot.config.gets.get('debug', False)

    async def get_account(self, user):
        async with self.bot.db.execute("""
            SELECT * FROM voyager_stats
            WHERE user_id = ?
        """, [user.id]) as cur:
            result = await cur.fetchone()
            return result

    async def create_account(self, user):
        await self.bot.db.execute("""
            INSERT INTO voyager_stats (user_id, total_gets, rank)
            VALUES (?, 0, 0)
        """, [user.id])

    async def commit_get(self, msg):
        log.debug('committing get for %s', msg)

        account = await self.get_account(msg.author)
        if account is None:
            await self.create_account(msg.author)
            account = await self.get_account(msg.author)  # bleh

        await self.bot.db.execute("""
            UPDATE voyager_stats
            SET total_gets = total_gets + 1, last_get = ?
            WHERE user_id = ?
        """, [datetime.datetime.utcnow(), msg.author.id])

        await self.bot.db.execute("""
            INSERT INTO voyager_gets (user_id, get_message_id, voyager_message_id, channel_id, guild_id)
            VALUES (?, ?, ?, ?, ?)
        """, [msg.author.id, msg.id, self.pending_get.id, msg.channel.id, msg.guild.id])

        past_rank = account[2]
        now_gets = account[1] + 1
        now_rank = get_rank(now_gets)
        now_rank_emoji = self.bot.emoji('get.' + str(now_rank))

        if past_rank != now_rank:
            # rank change
            await self.bot.db.execute("""
                UPDATE voyager_stats
                SET rank = ?
                WHERE user_id = ?
            """, [now_rank, msg.author.id])

            await msg.channel.send(
                '**You have leveled up!** '
                f'With {now_gets} GETs, you are now rank {now_rank_emoji}. Congratulations!'
            )

        if now_gets == 1:
            await msg.channel.send(
                f"**You just got your first GET!** You are now rank {now_rank_emoji} with {now_gets} GET(s)."
            )
        elif 1 < now_gets <= 5:
            await msg.channel.send(f'{now_rank_emoji} You now have {now_gets} GET(s).')
        else:
            await msg.channel.send(f'{now_rank_emoji} {now_gets - 1} \N{RIGHTWARDS ARROW} {now_gets}')

        await self.bot.db.commit()

        log.debug('committed get for %s', msg)

    async def on_message(self, msg):
        if (msg.webhook_id in self.webhooks and msg.channel.id in self.channels) or \
                (self.debug_mode and msg.content == '.get'):
            self.pending_get = msg
            return

        if msg.author.bot or self.pending_get is None:
            return

        await self.commit_get(msg)

        self.pending_get = None

    @group()
    @commands.check(get_channel)
    async def gets(self, ctx):
        """༼ つ ◕_◕ ༽つ TAKE MY GETS ༼ つ ◕_◕ ༽つ"""

    @gets.command()
    async def top(self, ctx):
        """Shows top getters"""
        await ctx.send('todo')

    @gets.command(aliases=['stats', 'info'])
    async def profile(self, ctx, target: discord.Member = None):
        """Shows your rank and info"""
        target = target or ctx.author
        account = await self.get_account(target)

        if account is None:
            subject = "You haven't" if target == ctx.author else f"{target} hasn't"
            await ctx.send(f"{ctx.tick(False)} {subject} collected any GETs yet.")
            return

        embed = discord.Embed(title=str(target), color=RANK_COLORS[account[2]])
        rank_emoji = ctx.bot.emoji(f'get.{account[2]}')
        last_ago = human_delta(account[3])
        embed.add_field(name='Current Rank', value=f'{rank_emoji} ({account[2]})')
        embed.add_field(name='Total GETs', value=str(account[1]))
        embed.add_field(name='Last GET', value=f'{last_ago} ago')
        await ctx.send(embed=embed)

    @gets.command()
    async def ranks(self, ctx):
        """Shows all ranks"""
        await ctx.send(RANK_INFO.format(*[ctx.bot.emoji(f'get.{num}') for num in range(0, 6)]))

    @gets.command(aliases=['what'])
    async def wtf(self, ctx):
        """Shows game info"""
        await ctx.send(GAME_INFO.format(prefix=ctx.prefix))


def setup(bot):
    bot.add_cog(Gets(bot))
