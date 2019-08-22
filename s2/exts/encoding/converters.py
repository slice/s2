import os.path
import tempfile
import typing as T
from yarl import URL

import lifesaver
from discord.ext import commands

SIZE_LIMIT = 8_000_000
SUPPORTED_EXTENSIONS = (".mp3", ".ogg", ".wav", ".flac")
SUPPORTED_EXTENSIONS_LISTING = ", ".join(f"`{ext}`" for ext in SUPPORTED_EXTENSIONS)
TOO_LARGE_MESSAGE = "Audio file is too large. Limit is 8 MB."
CDN_HOSTS = ["cdn.discordapp.com"]


class Audio(commands.Converter):
    """A converter to handle audio files.

    As a converter, it only handles CDN URLs. Attachment handling is exposed
    as a static method so that the argument can be optional when using an
    uploaded file. (Discord.py _needs_ an argument to convert when using
    converters. Because we'd like to not force the user to input something when
    uploading a file, this functionality is separated.)
    """

    async def _read_url(self, ctx: lifesaver.Context, url: URL) -> T.IO[T.Any]:
        filename = url.path.split("/")[-1]
        _, extension = os.path.splitext(filename)

        fp = tempfile.NamedTemporaryFile(suffix=extension)

        head_resp = await ctx.cog.session.head(url)
        try:
            content_length = int(head_resp.headers["content-length"])
        except ValueError:
            fp.close()
            raise commands.BadArgument(TOO_LARGE_MESSAGE)
        else:
            if content_length > SIZE_LIMIT:
                fp.close()
                raise commands.BadArgument(TOO_LARGE_MESSAGE)

        async with ctx.cog.session.get(url) as resp:
            fp.write(await resp.read())
            return fp

    @staticmethod
    async def handle_no_url_given(ctx: lifesaver.Context) -> T.IO[T.Any]:
        if ctx.message.attachments:
            return await Audio.read_attachment(ctx)

        raise commands.BadArgument(
            f"Provide an audio file ({SUPPORTED_EXTENSIONS_LISTING}) or a Discord CDN link to one."
        )

    @staticmethod
    async def read_attachment(ctx: lifesaver.Context) -> T.IO[T.Any]:
        try:
            attachment = next(
                attachment
                for attachment in ctx.message.attachments
                if attachment.filename.endswith(SUPPORTED_EXTENSIONS)
            )
        except StopIteration:
            raise commands.BadArgument(
                f"Unsupported audio format. Supported formats: {SUPPORTED_EXTENSIONS_LISTING}"
            )
        else:
            _, extension = os.path.splitext(attachment.filename)
            fp = tempfile.NamedTemporaryFile(suffix=extension)

            if attachment.size > SIZE_LIMIT:
                fp.close()
                raise commands.BadArgument(TOO_LARGE_MESSAGE)

            # Can't use `attachment.save(fp)` here becuase `_TemporaryFileWrapper`
            # isn't a proper subclass.
            fp.write(await attachment.read())

            return fp

    async def convert(self, ctx: lifesaver.Context, arg: str) -> T.IO[T.Any]:
        try:
            url = URL(arg)
        except ValueError:
            pass
        else:
            if url.host in CDN_HOSTS:
                return await self._read_url(ctx, url)
