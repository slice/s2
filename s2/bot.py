__all__ = ['S2']

import sqlite3

import aiosqlite
import lifesaver
from discord.ext import commands

from .schema import STATEMENTS


@lifesaver.command(name='info', aliases=['about'])
@commands.cooldown(1, 3, commands.BucketType.user)
async def command_info(ctx):
    """Shows information about the bot itself."""
    await ctx.send(f'This bot is owned by slice#0001 (`97104885337575424`).')


class S2(lifesaver.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.db = None
        self.add_command(command_info)

    async def setup_db(self):
        self.db = aiosqlite.connect('s2.db', loop=self.loop,
                                    detect_types=sqlite3.PARSE_DECLTYPES)

        # connect manually without a context manager
        self.db.start()
        await self.db._connect()

        # create tables as necessary
        await self.create_tables()

    async def on_ready(self):
        await super().on_ready()

        if self.db is None:
            await self.setup_db()

    async def create_tables(self):
        for statement in STATEMENTS:
            await self.db.execute(statement)

        await self.db.commit()

    async def close(self):
        # disconnect manually
        await self.db.close()
        self.db._connection = None

        await super().close()
