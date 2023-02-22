__all__ = ["S2"]

import sqlite3
import typing as T

import aiosqlite
import lifesaver

from .help import S2Help


class S2(lifesaver.Bot):
    def __init__(self, cfg: lifesaver.bot.BotConfig, **kwargs) -> None:
        super().__init__(
            cfg,
            help_command=S2Help(dm_help=cfg.dm_help, no_category="Commands"),
            **kwargs,
        )

        self.db: T.Optional[aiosqlite.Connection] = None

    async def _connect_to_db(self) -> None:
        self.db = await aiosqlite.connect(
            "s2.db", loop=self.loop, detect_types=sqlite3.PARSE_DECLTYPES
        )

    async def on_ready(self) -> None:
        await super().on_ready()

        self._hide_obvious_commands()

        if self.db is None:
            await self._connect_to_db()

    async def close(self) -> None:
        if self.db is not None:
            await self.db.close()

        await super().close()

    def _hide_obvious_commands(self) -> None:
        for name in {"help", "ping", "rtt", "jishaku"}:
            self._hide(name)

    def _hide(self, command_name: str) -> None:
        command = self.get_command(command_name)
        if command is not None:
            command.hidden = True
