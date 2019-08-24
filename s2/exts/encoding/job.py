import asyncio
import logging
import tempfile
import typing as T

import discord
import lifesaver

from .fkr import generate_args


class EncodingJob:
    def __init__(self, *, ctx, source: T.IO[T.Any], owner: discord.User) -> None:
        self.ctx = ctx
        self.source = source
        self.owner = owner
        self.log = logging.getLogger(f"encoding_job[{self.owner.id}]")

        self.output: T.IO[T.Any] = tempfile.NamedTemporaryFile(suffix=".mp3")
        self._proc: T.Optional[asyncio.subprocess.Process] = None

    def _log_stream(self, name: str, text: str) -> None:
        for line in text.splitlines():
            self.log.info("[%s] %s", name, line.decode())

    async def report(self, *args, **kwargs) -> discord.Message:
        can_send_messages = (
            self.ctx.channel.permissions_for(self.ctx.guild.me).send_messages
            if self.ctx.guild
            # always try to send to owner when in a dm
            else True
        )

        destination = self.ctx.channel if can_send_messages else self.owner

        try:
            return await destination.send(*args, **kwargs)
        except discord.HTTPException:
            # oof
            pass

    async def _delete_message(
        self, reaction: discord.Reaction, user: discord.abc.User
    ) -> None:
        try:
            await reaction.message.delete()
        except discord.HTTPException:
            pass

    async def _add_buttons(self, message: discord.Message) -> None:
        buttons = lifesaver.Buttons(message, owner=self.owner)
        buttons.on("\N{cross mark}", self._delete_message)
        await buttons.add_reactions()
        buttons.listen(self.ctx.bot)

    async def start(self) -> None:
        args = generate_args()

        flags = [
            # prevent noise
            "-loglevel",
            "warning",
            # overwrite existing files
            "-y",
            # input
            "-i",
            self.source.name,
            # encoder (always mp3)
            "-c:a",
            "libmp3lame",
            # downsized bitrate and filters
            *args,
            # output file
            self.output.name,
        ]

        self.log.info("$ ffmpeg %s", " ".join(flags))

        self._proc = await asyncio.create_subprocess_exec(
            "ffmpeg",
            *flags,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await self._proc.communicate()
        if stdout:
            self._log_stream("STDOUT", stdout)
        if stderr:
            self._log_stream("STDERR", stderr)

        if self._proc.returncode != 0:
            await self.report(
                "\N{warning sign} Something went wrong "
                "while encoding the audio! You may want to try that again. "
                f"{self.owner.mention}"
            )
        else:
            file = discord.File(self.output.name, filename="audio.mp3")
            info = f"Bitrate: {args[1]}bps. Filters: `{args[3]}`"
            message = await self.report(
                f"{self.ctx.tick()} Done. {info} {self.owner.mention}", file=file
            )
            await self._add_buttons(message)

        self.source.close()
        self.output.close()

        await self.ctx.cog._on_job_finish(self)

    def __repr__(self) -> str:
        return f"<EncodingJob owner={self.owner!r} source={self.source!r}>"
