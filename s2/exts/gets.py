import datetime
import logging

import discord
from discord.ext import commands
from lifesaver.bot import Cog, group
from lifesaver.utils import human_delta, Table, codeblock

log = logging.getLogger(__name__)

GAME_INFO = """A message sent directly after a build notification is a **GET.**
(GETs are only counted when they are in the same channel as the build notification.)

The total amount of GETs you collect determine your **rank.**
(To see the list of ranks, type `{prefix}gets ranks`.)

To see your total amount of GETs and other information about yourself like your rank, type `{prefix}gets profile`.
You can also use this command to view other people's profiles.
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
        self.pending_gets = {}

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

        pending_get = self.pending_gets[msg.channel.id]

        await self.bot.db.execute("""
            INSERT INTO voyager_gets (user_id, get_message_id, voyager_message_id, channel_id, guild_id)
            VALUES (?, ?, ?, ?, ?)
        """, [msg.author.id, msg.id, pending_get.id, msg.channel.id, msg.guild.id])

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
        if msg.channel.id not in self.channels:
            return

        if msg.webhook_id in self.webhooks:
            self.pending_gets[msg.channel.id] = msg
            return

        if msg.author.bot or msg.channel.id not in self.pending_gets:
            return

        await self.commit_get(msg)

        del self.pending_gets[msg.channel.id]

    @group()
    @commands.check(get_channel)
    async def gets(self, ctx):
        """༼ つ ◕_◕ ༽つ TAKE MY GETS ༼ つ ◕_◕ ༽つ"""

    @gets.command()
    async def top(self, ctx):
        """Shows top getters"""
        table = Table('User', 'Total GETs', 'Rank')

        async with ctx.bot.db.execute("""
            SELECT * FROM voyager_stats
            ORDER BY total_gets DESC
            LIMIT 10
        """) as cur:
            async for row in cur:
                user = ctx.bot.get_user(row[0])
                if not user:
                    user = '???'
                table.add_row(str(user), str(row[1]), str(row[2]))

        await ctx.send(codeblock(await table.render(ctx.bot.loop)))

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
