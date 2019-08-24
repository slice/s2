import asyncio
import os.path
import typing as T

import discord
import lifesaver
from discord.ext import commands

from .job import EncodingJob
from .converters import Audio, SUPPORTED_EXTENSIONS_LISTING

MAXIMUM_JOBS_RUNNING = 3


class Encoding(lifesaver.Cog):
    def __init__(self, bot) -> None:
        super().__init__(bot)
        self.jobs = []
        self.jobs_lock = asyncio.Lock()

    @lifesaver.command(name="audiofkr", aliases=["audiofucker", "af"])
    @commands.cooldown(1, 5, type=commands.BucketType.user)
    async def command_audiofkr(
        self, ctx: lifesaver.Context, *, audio: T.Optional[Audio]
    ):
        """fucks some audio"""
        if audio is None:
            # Use the attached audio file. If there isn't one, `commands.BadArgument`
            # is raised.
            audio = await Audio.handle_no_url_given(ctx)

        self.log.info("audio: %r @ %s", audio, audio.name)

        async with self.jobs_lock:
            job = EncodingJob(ctx=ctx, source=audio, owner=ctx.author)
            self.jobs.append(job)
            self.log.info("starting %r", job)
            ctx.bot.loop.create_task(job.start())

    @command_audiofkr.before_invoke
    async def before_audiofkr(self, ctx):
        if discord.utils.find(lambda job: job.owner == ctx.author, self.jobs):
            raise commands.BadArgument("You are already encoding a file.")

        if len(self.jobs) >= MAXIMUM_JOBS_RUNNING:
            raise commands.BadArgument(
                "Too many audio files are being encoded right now. Please try again later."
            )

    async def _on_job_finish(self, job):
        self.log.info("finished with %r", job)
        async with self.jobs_lock:
            self.jobs.remove(job)


def setup(bot):
    bot.add_cog(Encoding(bot))
