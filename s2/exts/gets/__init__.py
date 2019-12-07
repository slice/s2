import asyncio
import collections
import logging

import discord
import lifesaver
from discord.ext import commands
from lifesaver.utils import human_delta, pluralize

from .checks import get_channel
from .config import GetsConfig
from .database import GetsDatabase
from .strings import GAME_INFO, LEADERBOARD_MEDALS
from .waiting import wait_for_n_messages

log = logging.getLogger(__name__)


@lifesaver.Cog.with_config(GetsConfig)
class Gets(lifesaver.Cog):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.db = GetsDatabase(self.bot)

        #: A list of messages from VersionVoyager that haven't been GETted yet.
        #: This is a :class:`collections.defaultdict`, with guild ID keys and a
        #: list of :class:`discord.Message`s for the values.
        self.pending_gets = collections.defaultdict(list)

        #: A :class:`collections.defaultdict` of guild IDs to :class:`asyncio.Lock`s.
        #: Used to ensure that there aren't any race conditions.
        self.locks = collections.defaultdict(asyncio.Lock)

    async def process_get(self, msg: discord.Message):
        """Process an earned GET from a message."""
        log.debug("processing get grab (message: %r)", msg)

        account = await self.db.ensure_account(msg.author)

        get_messages = self.pending_gets[msg.guild.id]
        earned = len(get_messages)

        # update total amount of gets earned
        await self.db.add_gets(msg.author, earned)

        # add the individual get
        await self.bot.db.execute(
            """
            INSERT INTO voyager_gets (user_id, get_message_id, voyager_message_id, channel_id, guild_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            [msg.author.id, msg.id, get_messages[-1].id, msg.channel.id, msg.guild.id],
        )

        new_total = account[1] + earned

        await self.bot.db.commit()
        log.debug(
            "committed get grab to database (target: %r, new_total: %d)",
            msg.author,
            new_total,
        )

        win_message = f"{new_total:,}"

        if earned > 1:
            win_message += f" (+{earned:,})"

        notice = await msg.channel.send(win_message)

        def other_message_check(incoming_msg: discord.Message) -> bool:
            return (
                incoming_msg.channel == msg.channel
                and incoming_msg.author != msg.author
                and not incoming_msg.author.bot
            )

        # elaborate on the earner of the gets if another message is quickly sent
        # after the get was earned.
        if await wait_for_n_messages(
            self.bot, msg.channel, messages=1, timeout=3, check=other_message_check
        ):
            log.debug("elaborating get earner (notice: %r)", notice)
            await notice.edit(content=f"{msg.author.name}  \xb7  {win_message}")

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

    @lifesaver.group(aliases=["g"], hollow=True)
    @commands.check(get_channel)
    async def gets(self, ctx):
        """mary consumed my arteries"""

    @gets.command(aliases=["leaderboard"])
    async def top(self, ctx):
        """Shows the top GET earners"""

        users = await self.db.get_top_getters(10)

        embed = discord.Embed(title="GET Leaderboard")

        def format_row(index, row):
            user_id = row[0]
            total_gets = row[1]
            user = ctx.bot.get_user(user_id)
            gets = pluralize(get=total_gets, with_quantity=False)

            if not user:
                user = "???"

            if index < 3:
                medal = LEADERBOARD_MEDALS[index]
                return f"{medal} **{user}** ({total_gets:,} {gets})"

            return f"{index + 1}. {user} ({total_gets:,} {gets})"

        listing = [format_row(index, row) for index, row in enumerate(users)]

        embed.add_field(name="Top 3", value="\n".join(listing[:3]), inline=False)

        others = users[3:]
        if others:
            embed.add_field(
                name="Runner-ups", value="\n".join(listing[3:]), inline=False
            )

        embed.set_footer(text="An efficient use of human energy indeed.")
        await ctx.send(embed=embed)

    @gets.command(aliases=["stats", "info"])
    async def profile(self, ctx, target: discord.Member = None):
        """Shows your profile"""
        target = target or ctx.author
        account = await self.db.fetch_account(target)

        if account is None:
            subject = "You haven't" if target == ctx.author else f"{target} hasn't"
            await ctx.send(f"{ctx.tick(False)} {subject} collected any GETs yet.")
            return

        embed = discord.Embed(title=str(target))
        last_ago = human_delta(account[3])
        embed.add_field(name="Total GETs", value=f"{account[1]:,}")
        embed.add_field(name="Last GET", value=f"{last_ago} ago")
        await ctx.send(embed=embed)

    @gets.command(hidden=True)
    @commands.is_owner()
    async def write(self, ctx, target: discord.Member, amount: int):
        """Writes the amount of GETs for a user"""
        await self.db.set_gets(target, amount)
        await self.bot.db.commit()
        await ctx.ok()

    @gets.command(hidden=True)
    @commands.is_owner()
    async def sink(self, ctx, target: discord.Member):
        """Deletes all of someone's GETs

        to be used when mary trashtalks react >:c
        """
        await self.db.set_gets(target, 0)
        await self.bot.db.commit()
        await ctx.ok()

    @gets.command(aliases=["wtf", "what", "tut"])
    async def tutorial(self, ctx):
        """Shows game tutorial"""
        game_info = GAME_INFO.format(prefix=ctx.prefix)
        if ctx.can_send_embeds:
            embed = discord.Embed(
                title="How to earn GETs",
                description=game_info,
                color=discord.Color.blue(),
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send(game_info)


def setup(bot):
    bot.add_cog(Gets(bot))
