import asyncio
import datetime
import logging
import typing
from collections import defaultdict

import discord
import lifesaver
from discord.ext import commands
from lifesaver.utils import human_delta, pluralize

log = logging.getLogger(__name__)

GAME_INFO = """A message sent directly after a build notification is a **GET.**
(GETs are only counted when they are in the same channel as the build notification.)

To see your total amount of GETs and other information about yourself, type `{prefix}gets profile`.
You can also use this command to view other people's profiles.
"""


LEADERBOARD_MEDALS = [
    '\N{FIRST PLACE MEDAL}',
    '\N{SECOND PLACE MEDAL}',
    '\N{THIRD PLACE MEDAL}',
]


def get_channel(ctx):
    """A check that enforces commands to only be runnable from GET channels."""
    return ctx.channel.id in ctx.cog.config.channels


async def wait_for_n_messages(bot, channel, *, messages: int, timeout: int, check=None) -> bool:
    """Wait for a certain amount of messages to pass in a window of time.

    Returns whether the number of messages was reached.
    """

    def default_check(msg):
        return msg.channel == channel

    async def message_counter():
        amount = 0

        while True:
            await bot.wait_for('message', check=check or default_check)
            amount += 1

            if amount >= messages:
                return

    try:
        await asyncio.wait_for(message_counter(), timeout=timeout, loop=bot.loop)
    except asyncio.TimeoutError:
        return False

    return True


class GetsConfig(lifesaver.config.Config):
    webhooks: typing.List[int]
    channels: typing.List[int]
    debug: bool


@lifesaver.Cog.with_config(GetsConfig)
class Gets(lifesaver.Cog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pending_gets = defaultdict(list)
        self.locks = defaultdict(asyncio.Lock)

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

    async def process_get(self, msg: discord.Message):
        """Process an earned GET from a message."""
        log.debug('processing get grab (message: %r)', msg)

        account = await self.get_account(msg.author)
        if account is None:
            # automatically create an account
            await self.create_account(msg.author)
            account = await self.get_account(msg.author)

        get_messages = self.pending_gets[msg.guild.id]
        earned = len(get_messages)

        # update total amount of gets earned
        await self.bot.db.execute("""
            UPDATE voyager_stats
            SET total_gets = total_gets + ?, last_get = ?
            WHERE user_id = ?
        """, [earned, datetime.datetime.utcnow(), msg.author.id])

        # add the individual get
        await self.bot.db.execute("""
            INSERT INTO voyager_gets (user_id, get_message_id, voyager_message_id, channel_id, guild_id)
            VALUES (?, ?, ?, ?, ?)
        """, [msg.author.id, msg.id, get_messages[-1].id, msg.channel.id, msg.guild.id])

        new_total = account[1] + earned

        await self.bot.db.commit()
        log.debug('committed get grab to database (target: %r, new_total: %d)', msg.author, new_total)

        win_message = str(new_total)

        if earned > 1:
            win_message += f' (+{earned})'

        notice = await msg.channel.send(win_message)

        def other_message_check(incoming_msg):
            return (
                incoming_msg.channel == msg.channel
                and incoming_msg.author != msg.author
                and not incoming_msg.author.bot
            )

        # elaborate on the earner of the gets if another message is quickly sent
        # after the get was earned.
        if await wait_for_n_messages(self.bot, msg.channel, messages=1, timeout=3, check=other_message_check):
            log.debug('elaborating get earner (notice: %r)', notice)
            await notice.edit(content=f'{msg.author.name}  \xb7  {win_message}')

    @lifesaver.Cog.listener()
    async def on_message(self, msg):
        if msg.webhook_id in self.config.webhooks:
            self.pending_gets[msg.guild.id].append(msg)
            return

        if msg.channel.id not in self.config.channels:
            return

        async with self.locks[msg.guild.id]:
            if msg.author.bot or msg.guild.id not in self.pending_gets:
                return

            await self.process_get(msg)
            del self.pending_gets[msg.guild.id]

    @lifesaver.group()
    @commands.check(get_channel)
    async def gets(self, ctx):
        """༼ つ ◕_◕ ༽つ TAKE MY GETS ༼ つ ◕_◕ ༽つ"""

    @gets.command(aliases=['leaderboard'])
    async def top(self, ctx):
        """Shows the top GETters"""

        async with ctx.bot.db.execute("""
            SELECT * FROM voyager_stats
            ORDER BY total_gets DESC
            LIMIT 10
        """) as cur:
            users = await cur.fetchall()

        embed = discord.Embed(title='GET Leaderboard')

        def format_row(index, row):
            user_id = row[0]
            total_gets = row[1]
            user = ctx.bot.get_user(user_id)
            gets = pluralize(get=total_gets)

            if not user:
                user = '???'

            if index < 3:
                medal = LEADERBOARD_MEDALS[index]
                return f'{medal} **{user}** ({gets})'

            return f'{index + 1}. {user} ({gets})'

        listing = [
            format_row(index, row)
            for index, row in enumerate(users)
        ]

        embed.add_field(name='Top 3', value='\n'.join(listing[:3]), inline=False)

        others = users[3:]
        if others:
            embed.add_field(
                name='Runner-ups',
                value='\n'.join(listing[3:]),
                inline=False
            )

        embed.set_footer(text='An efficient use of human energy indeed.')
        await ctx.send(embed=embed)

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
