import datetime

import aiohttp
import discord
from discord.ext import commands
from lifesaver.bot import command, Cog
from lifesaver.utils.formatting import human_delta
from lifesaver.utils.timing import format_seconds

MEDALS = ['\N{FIRST PLACE MEDAL}', '\N{SECOND PLACE MEDAL}', '\N{THIRD PLACE MEDAL}']
COMPLETION_SYMBOLS = ['\N{NEW MOON SYMBOL}', '\N{LAST QUARTER MOON SYMBOL}', '\N{FULL MOON SYMBOL}']


def to_utc(date):
    return date.astimezone(datetime.timezone.utc).replace(tzinfo=None)


class AOC(Cog):
    def __init__(self, bot):
        super().__init__(bot)
        aoc = bot.config.aoc
        self.event = aoc['event']
        self.leaderboard_id = aoc['leaderboard_id']
        self.session_secret = aoc['session_secret']

        self.headers = {'User-Agent': 's2/0.0.0 (https://github.com/slice)'}
        self.endpoint = 'https://adventofcode.com/{event}/leaderboard/private/view/{board}.json'.format(
            event=self.event,
            board=self.leaderboard_id,
        )
        self.cookies = {'session': aoc['session_secret']}

    def est_now(self):
        """Returns the current time in EST."""
        timezone = datetime.timezone(datetime.timedelta(hours=-5))
        return datetime.datetime.now(timezone)

    def is_aoc(self):
        return self.est_now().month == 12

    def current_date(self, day=None):
        """Returns the beginning of a day's date. Defaults to the current day."""
        return self.est_now().replace(day=day or self.current_day(), hour=0, minute=0, second=0)

    def current_day(self):
        """Returns the current day number of the event."""
        date = self.est_now()

        if date.hour >= 0:
            # after midnight, the day started!
            return date.day
        else:
            # not yet midnight, it's still the previous day
            return date.day - 1

    def next_date(self):
        """Returns the beginning of the next day's date."""
        date = self.est_now()
        current_day = self.current_day()

        if date.day > current_day:
            # it's not midnight est or later yet, so the next day would be today
            return date.replace(hour=0, minute=0, second=0)
        else:
            # the current day matches up with the date, it's active. so it would
            # be tomorrow
            return date.replace(day=date.day + 1, hour=0, minute=0, second=0)

    @command()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.cooldown(1, 2, commands.BucketType.channel)
    async def aoc(self, ctx, day: int = None):
        """Shows the Advent of Code leaderboard."""
        if not self.is_aoc():
            await ctx.send("advent of code is over :(")
            return

        if day is not None and (day < 1 or day > self.current_day()):
            await ctx.send("no. try again!")
            return

        async with aiohttp.ClientSession(headers=self.headers, cookies=self.cookies) as sess:
            async with sess.get(self.endpoint) as resp:
                data = await resp.json()

        embed = discord.Embed(title=f'Advent of Code {self.event}')
        members = list(data['members'].values())
        members = sorted(members, key=lambda member: member['local_score'], reverse=True)

        if day is None or (day is not None and day == self.current_day()):
            # if no day was provided or the day provided is today, show today
            day = self.current_day()
            next_day_utc = to_utc(self.next_date())
            next_day_ts = human_delta(next_day_utc - datetime.datetime.utcnow())
            embed.description = (f"It's day {day} of AOC {self.event}. "
                                 f"Day {day + 1} starts in {next_day_ts}.")
        else:
            # historical stuff
            embed.description = f'Showing historical stats for day {day}.'

        def format_part_completion(member, part):
            """Format how long it took someone to solve a part of a day."""
            stamps = member['completion_day_level'][str(day)]
            timestamp = datetime.datetime.utcfromtimestamp(int(stamps[str(part)]['get_star_ts']))
            if part == 2:
                # become relative from p1 instead of from day start
                start = datetime.datetime.utcfromtimestamp(int(stamps['1']['get_star_ts']))
            else:
                start = to_utc(self.current_date(day))
            delta = timestamp.replace(second=0) - start.replace(second=0, microsecond=0)
            return human_delta(delta).replace(', ', '').replace(' and ', '')

        def format_member(index, member):
            name = member['name']
            score = member['local_score']

            got_first = str(day) in member.get('completion_day_level', {})
            got_second = '2' in member.get('completion_day_level', {}).get(str(day), {})
            emoji = COMPLETION_SYMBOLS[got_first + got_second]

            if got_first:
                comp_delta = f' (took {format_part_completion(member, 1)}'
                if got_second:
                    comp_delta += f' + {format_part_completion(member, 2)}'
                comp_delta += ')'
            else:
                comp_delta = ''

            if index < 3:
                return f'{emoji} {MEDALS[index]} **{score}\N{BLACK STAR} {name}**{comp_delta}'
            else:
                return f'{emoji} `{index + 1}.` {score}\N{BLACK STAR} {name}{comp_delta}'

        def format_listing(members):
            return '\n'.join(map(format_member, enumerate(members)))

        embed.add_field(
            name='Top 3',
            value='\n'.join(format_member(index, member) for (index, member) in enumerate(members[:3])),
        )
        embed.add_field(
            name='Runner-ups',
            value='\n'.join(format_member(index + 3, member) for (index, member) in enumerate(members[3:15])),
        )

        await ctx.send(embed=embed)

    @aoc.error
    async def aoc_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            stamp = format_seconds(error.retry_after)
            await ctx.send(f"you're doing that too fast! retry in {stamp}.")


def setup(bot):
    bot.add_cog(AOC(bot))
