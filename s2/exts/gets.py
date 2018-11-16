import asyncio
import datetime
import logging
from collections import defaultdict
from random import choice

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

RANKUP_FLAVOR = [
    "Nice one!",
    "weird flex but okay.",
    "LEVEL UP!",
    "You've gone up a level.",
    "You totally deserve this.",
    "okay, this is epic.",
    "Feeling bored yet?",
    "Nice to see that you're still wasting your lifespan on this.",
    "Umm...",
    "Well, okay.",
    "You sure about this?",
    "Sigh...",
    "Sheesh.",
    "\\*internal screaming\\*",
    "\\*cough\\*",
    "Oh god.",
    "Oh no!",
    "おめでとう！",
    "Umm, okay.",
    "Huh?",
]


SALMON = discord.Color(0xff7e79)
CANTALOUPE = discord.Color(0xffd479)
BANANA = discord.Color(0xfffc79)
RANKS = [
    # --- base ranks
    {'range': (0, 10), 'color': discord.Color(0x45e6e5),
     'flavor': ["It's smart yet humble. Likes to rotate when nobody is around.",
                "It's a passionate square.", "It's a cyan square. Scratch and sniff compatible."]},
    {'range': (11, 20), 'color': discord.Color(0x457ae5),
     'flavor': ["Likes to wear a hat sometimes.", "Has a strong preference "
                "towards vanilla ice cream.", "Likes to play basketball."]},
    {'range': (21, 40), 'color': discord.Color(0x7a45e5),
     'flavor': ["A quiet hexagon. Wears glasses but doesn't need them.",
                "Really addicted to anime somehow.", "Smells like grapes."]},
    {'range': (41, 60), 'color': discord.Color(0xe545e5),
     'flavor': ["Shy heptagon. Wants to be popular with today's generation.",
                "Constantly has headphones on.", "Writes a lot of JavaScript."]},
    {'range': (61, 80), 'color': discord.Color(0xe545b0),
     'flavor': ["A rounded octagon. Looks like it has pink hair dye on.",
                "It makes eye contact and looks away quickly.", '"Oh, hi."']},
    {'range': (81, 100), 'color': discord.Color(0xe54545),
     'flavor': ["An ominous red circle. It's actually pretty nice once you "
                "get to know it.", '"But steel is heavier than feathers..."',
                "Isn't the smartest, but it loves its friends a lot."]},

    # --- circles
    {'range': (101, 110), 'color': BANANA,
     'flavor': ["Blushes too much.", "Takes compliments too far.",
                "Follows you on the fediverse."]},
    {'range': (111, 120), 'color': CANTALOUPE,
     'flavor': ["Wants to kill every spider on this planet.",
                "Likes to think about life.", "Prefers `yarn` over `npm`."]},
    {'range': (121, 130), 'color': SALMON,
     'flavor': ["Covered in cherry sauce.", "Smells like strawberry.",
                'Always says "hello" awkwardly.', "Watches too much YouTube."]},

    # --- arrows
    {'range': (131, 140), 'color': BANANA,
     'flavor': ["Writes open source software for the masses.",
                "Owns 5 dogs. It pets them constantly.", "Likes to keep "
                "everything clean."]},
    {'range': (141, 150), 'color': CANTALOUPE,
     'flavor': ["Starved of physical affection...", "Needs a hug.",
                "Talks a lot about its love interests."]},
    {'range': (151, 160), 'color': SALMON,
     'flavor': ["Likes to point to interesting things.", "Often used by "
                "pedestrians and drivers all around the world.", "Likes to "
                "flex its disproportionately large muscles..."]},

    # --- bookmarks
    {'range': (161, 170), 'color': BANANA,
     'flavor': ["It already likes you.", "Thinks it's too cold in this room.",
                "Likes to read books a lot. Makes frequent trips to the library."]},
    {'range': (171, 180), 'color': CANTALOUPE,
     'flavor': ["Mildly annoying, but also charming.", "Pretends to hate you, "
                "but actually likes you. Huh.", "The most tsundere of ranks."]},
    {'range': (181, 190), 'color': SALMON,
     'flavor': ["Likes to play the saxophone.", "Sleeps too much.",
                "Is often found alone.", "Likes to make wishes."]},
]


def get_channel(ctx):
    return ctx.channel.id in ctx.cog.channels


def get_rank(n_gets: int) -> int:
    rank = discord.utils.find(
        lambda rank: n_gets in range(rank['range'][0], rank['range'][1] + 1),
        RANKS,
    )

    if rank:
        return rank
    else:
        return RANKS[-1]


class Gets(Cog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pending_gets = {}
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

        pending_get = self.pending_gets[msg.guild.id]

        await self.bot.db.execute("""
            INSERT INTO voyager_gets (user_id, get_message_id, voyager_message_id, channel_id, guild_id)
            VALUES (?, ?, ?, ?, ?)
        """, [msg.author.id, msg.id, pending_get.id, msg.channel.id, msg.guild.id])

        past_rank = account[2]
        now_gets = account[1] + 1

        now_rank = get_rank(now_gets)
        now_rank_n = RANKS.index(now_rank)
        now_rank_emoji = self.bot.emoji(f'get.{now_rank_n}')
        flavor = choice(now_rank['flavor'])

        if past_rank != now_rank_n:
            await self.bot.db.execute("""
                UPDATE voyager_stats
                SET rank = ?
                WHERE user_id = ?
            """, [now_rank_n, msg.author.id])

            await msg.channel.send(
                f'**{choice(RANKUP_FLAVOR)}** You are now rank {now_rank_emoji}.'
                f'\n\n**{now_rank_emoji} info:** {flavor}'
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
        if msg.webhook_id in self.webhooks:
            self.pending_gets[msg.guild.id] = msg
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

        rank = RANKS[account[2]]

        embed = discord.Embed(title=str(target), color=rank['color'])
        rank_emoji = ctx.bot.emoji(f'get.{account[2]}')
        last_ago = human_delta(account[3])
        embed.add_field(name='Current Rank', value=f'{rank_emoji} ({account[2]})')
        embed.add_field(name='Total GETs', value=str(account[1]))
        embed.add_field(name='Last GET', value=f'{last_ago} ago')
        await ctx.send(embed=embed)

    @gets.command(hidden=True)
    @commands.is_owner()
    async def write(self, ctx, target: discord.Member, amount: int):
        """Writes GET amount for a user"""
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

    @gets.command()
    async def ranks(self, ctx):
        """Shows all ranks"""
        ctx.new_paginator(prefix='', suffix='')
        for n, rank in enumerate(RANKS):
            emoji = self.bot.emoji(f'get.{n}')
            ctx += f'{emoji} @ {rank["range"][0]} GETs'
        await ctx.send_pages()

    @gets.command(aliases=['what'])
    async def wtf(self, ctx):
        """Shows game info"""
        await ctx.send(GAME_INFO.format(prefix=ctx.prefix))


def setup(bot):
    bot.add_cog(Gets(bot))
