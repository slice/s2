__all__ = ["S2"]

import sqlite3

import aiosqlite
import lifesaver

from .schema import STATEMENTS


class S2(lifesaver.Bot):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.db = None

    async def setup_db(self) -> None:
        self.db = aiosqlite.connect(
            "s2.db", loop=self.loop, detect_types=sqlite3.PARSE_DECLTYPES
        )

        # connect manually without a context manager
        self.db.start()
        await self.db._connect()

        # create tables as necessary
        await self.create_tables()

    async def on_ready(self) -> None:
        await super().on_ready()

        self._hide_obvious_commands()

        if self.db is None:
            await self.setup_db()

    async def create_tables(self) -> None:
        for statement in STATEMENTS:
            await self.db.execute(statement)

        await self.db.commit()

    async def close(self) -> None:
        # disconnect manually
        await self.db.close()
        self.db._connection = None

        await super().close()

    def _hide_obvious_commands(self) -> None:
        for name in {"help", "ping", "rtt", "jishaku"}:
            self._hide(name)

    def _hide(self, command_name: str) -> None:
        command = self.get_command(command_name)
        if command:
            command.hidden = True
