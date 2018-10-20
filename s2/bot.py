import sqlite3

__all__ = ['S2']

import aiosqlite
from lifesaver.bot import Bot


class S2(Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.db = None

    async def on_ready(self):
        await super().on_ready()
        self.db = aiosqlite.connect('s2.db', loop=self.loop, detect_types=sqlite3.PARSE_DECLTYPES)

        # connect manually without a context manager
        self.db.start()
        await self.db._connect()

        await self.create_tables()

    async def create_tables(self):
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS voyager_gets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id BIGINT,
                get_message_id BIGINT,
                voyager_message_id BIGINT,
                channel_id BIGINT,
                guild_id BIGINT
            )
        """)

        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS voyager_stats (
                user_id BIGINT PRIMARY KEY,
                total_gets INTEGER,
                rank INTEGER,
                last_get TIMESTAMP
            )
        """)

        await self.db.commit()

    async def close(self):
        # disconnect manually
        await self.db.close()
        self.db._connection = None

        await super().close()
