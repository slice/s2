import asyncio
import contextlib
import logging
from collections import defaultdict

import aiosqlite
import discord
import lifesaver
from discord.ext import commands
from lifesaver.utils import human_delta, pluralize

from .checks import get_zone_only
from .config import GetsConfig
from .database import GetsDatabase
from .strings import GAME_INFO, LEADERBOARD_MEDALS, COLORS
from .waiting import wait_for_n_messages

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)  # >:O


def message_ineligible(msg: discord.Message) -> bool:
    stop_phrase = "[gets:prohibit]"

    def embed_contains_stop(embed: discord.Embed) -> bool:
        return stop_phrase in (embed.footer.text or "") or \
                stop_phrase in (embed.description or "")  # fmt: skip

    return stop_phrase in msg.content or any(
        embed_contains_stop(embed) for embed in msg.embeds
    )


@lifesaver.Cog.with_config(GetsConfig)
class Gets(lifesaver.Cog):
    config: GetsConfig

    def __init__(self, bot: lifesaver.Bot) -> None:
        super().__init__(bot)
        self.db = GetsDatabase(self.bot)

        #: A list of messages from VersionVoyager that haven't been GETted yet.
        #: This is a :class:`collections.defaultdict`, with guild ID keys and a
        #: list of :class:`discord.Message`s for the values.
        self.pending_gets: defaultdict[int, list[discord.Message]] = defaultdict(list)

        #: The global transaction lock. This should be locked when any kind of
        #: transaction is taking place (e.g. adding GETs or updating an
        #: account's total GETs.)
        self.transaction_lock = asyncio.Lock()

        #: A :class:`collections.defaultdict` of guild IDs to :class:`asyncio.Lock`s.
        #: Used to ensure that there aren't any race conditions.
        self.locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

    @property
    def sqlite(self) -> aiosqlite.Connection:
        return self.bot.db  # type: ignore

    async def process_get(self, msg: discord.Message) -> None:
        """Process an earned GET from a message."""
        assert msg.guild is not None

        log.debug(
            "Processing earned GET (message: %d, obtainer: %d)", msg.id, msg.author.id
        )

        async with self.transaction_lock:
            account = await self.db.ensure_account(msg.author)

            voyager_messages = self.pending_gets[msg.guild.id]
            gets_earned = len(voyager_messages)

            # update total amount of gets earned
            await self.db.add_gets(msg.author, gets_earned)

            individual_get_params = [
                [
                    msg.author.id,
                    msg.id,
                    voyager_message.id,
                    msg.channel.id,
                    msg.guild.id,
                ]
                for voyager_message in voyager_messages
            ]

            # track the individual gets for each voyager message earned
            await self.sqlite.executemany(
                """
                INSERT INTO voyager_gets (user_id, get_message_id, voyager_message_id, channel_id, guild_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                individual_get_params,
            )

            new_total = account[1] + gets_earned

            await self.sqlite.commit()
            log.debug(
                "Committed GET to database (obtainer: %r, new_total: %d, gets_earned: %d)",
                msg.author.id,
                new_total,
                gets_earned,
            )

        win_message = f"{new_total:,}"

        if gets_earned > 1:
            win_message += f" (+{gets_earned:,})"

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
            log.debug("Elaborating GET obtainer (notice: %r)", notice)
            await notice.edit(content=f"{msg.author.name}  \xb7  {win_message}")

    async def prime_get(self, msg: discord.Message) -> None:
        if message_ineligible(msg):
            log.debug(
                "Not going to prime message %d, it's prohibited from GETs", msg.id
            )
            with contextlib.suppress(discord.HTTPException):
                await msg.add_reaction("\N{NO ENTRY SIGN}")
            return

        assert msg.guild is not None
        self.pending_gets[msg.guild.id].append(msg)
        log.debug(
            "Primed message %d in guild %d from webhook %d for a GET",
            msg.id,
            msg.guild.id,
            msg.webhook_id,
        )

    @lifesaver.Cog.listener()
    async def on_message(self, msg: discord.Message):
        if msg.channel.id not in self.config.get_channels:
            return
        assert msg.guild is not None

        async with self.locks[msg.guild.id]:
            if msg.webhook_id in self.config.webhooks:
                await self.prime_get(msg)
                return

            if msg.author.bot:
                log.debug("Ignoring GET-collecting message %d, from a bot", msg.id)
                return

            if msg.guild.id not in self.pending_gets:
                log.debug(
                    "Ignoring message %d, there are no pending GETs in guild %d",
                    msg.id,
                    msg.guild.id,
                )
                return

            await self.process_get(msg)
            del self.pending_gets[msg.guild.id]
            log.info(
                "Finished processing GET from message %d in guild %d", msg, msg.guild.id
            )

    @lifesaver.group(aliases=["g"], hollow=True)
    @commands.check(get_zone_only)
    async def gets(self, _: lifesaver.Context):
        """mary consumed my arteries"""

    @gets.command(aliases=["leaderboard"])
    async def top(self, ctx: lifesaver.Context):
        """Shows the top GET earners"""

        users = await self.db.get_top_getters(10)

        embed = discord.Embed(title="GET Leaderboard")

        def format_row(index: int, row: "aiosqlite.Row") -> str:
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

    @gets.command(aliases=["p"])
    async def profile(
        self, ctx: lifesaver.Context, target: discord.Member = commands.Author
    ):
        """See useful information about a game participant"""
        account = await self.db.fetch_account(target)

        if account is None:
            subject = "You haven't" if target == ctx.author else f"{target} hasn't"
            await ctx.send(f"{ctx.tick(False)} {subject} doesn't have any GETs yet.")
            return

        colors = [getattr(discord.Color, color_name)() for color_name in COLORS]
        color = colors[target.id % len(colors)]

        embed = discord.Embed(title=f"{account[1]:,} GETs", color=color)
        embed.set_author(icon_url=str(target.avatar), name=str(target))
        last_ago = human_delta(account[3])
        embed.add_field(name="Last GET", value=f"{last_ago} ago", inline=False)
        await ctx.send(embed=embed)

    @gets.command(hidden=True)
    @commands.is_owner()
    async def write(self, ctx: lifesaver.Context, target: discord.Member, amount: int):
        """Overwrite someone's GET balance

        This only changes the stored total; individual records of obtained GETs
        are unaffected.
        """
        async with self.transaction_lock:
            await self.db.set_gets(target, amount)
            await self.sqlite.commit()
        await ctx.ok()

    @gets.command(hidden=True)
    @commands.is_owner()
    async def sink(self, ctx: lifesaver.Context, target: discord.Member):
        """Set someone's GET balance to zero

        This only changes the stored total; individual records of obtained GETs
        are unaffected.
        """
        async with self.transaction_lock:
            await self.db.set_gets(target, 0)
            await self.sqlite.commit()
        await ctx.ok()

    @gets.command(aliases=["wtf", "what", "tut"])
    async def tutorial(self, ctx: lifesaver.Context):
        """See game instructions"""
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


async def setup(bot: lifesaver.Bot) -> None:
    await bot.add_cog(Gets(bot))
