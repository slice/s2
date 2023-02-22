__all__ = ["GetsDatabase"]

import datetime
from typing import Optional

import aiosqlite
import lifesaver
import discord

Person = discord.User | discord.Member


class GetsDatabase:
    def __init__(self, bot: lifesaver.Bot) -> None:
        self.bot = bot

    @property
    def db(self) -> aiosqlite.Connection:
        return self.bot.db  # type: ignore

    async def get_top_getters(self, n: int) -> list[aiosqlite.Row]:
        """Fetch the top GETters."""
        async with self.db.execute(
            """
            SELECT *
            FROM voyager_stats
            ORDER BY total_gets DESC
            LIMIT ?
            """,
            [n],
        ) as cur:
            return list(await cur.fetchall())

    async def fetch_account(self, user: Person) -> Optional[aiosqlite.Row]:
        """Fetch account information for a user."""
        async with self.db.execute(
            """
            SELECT *
            FROM voyager_stats
            WHERE user_id = ?
            LIMIT 1
            """,
            [user.id],
        ) as cur:
            result = await cur.fetchone()
            return result

    async def ensure_account(self, user: Person) -> aiosqlite.Row:
        """Fetch account information for a user.

        The account is created if it doesn't exist.
        """
        account = await self.fetch_account(user)
        if account:
            return account
        else:
            await self.create_account(user)
            new_account = await self.fetch_account(user)
            assert new_account is not None
            return new_account

    async def set_gets(self, user: Person, amount: int) -> None:
        """Set a user's total GET count."""
        await self.db.execute(
            """
            UPDATE voyager_stats
            SET total_gets = ?
            WHERE user_id = ?
            """,
            [amount, user.id],
        )

    async def add_gets(self, user: Person, amount: int) -> None:
        """Add to a user's total GET count."""
        await self.db.execute(
            """
            UPDATE voyager_stats
            SET total_gets = total_gets + ?, last_get = ?
            WHERE user_id = ?
            """,
            [amount, datetime.datetime.utcnow(), user.id],
        )

    async def create_account(self, user: Person) -> None:
        """Create an account for a user."""
        await self.db.execute(
            """
            INSERT INTO voyager_stats (user_id, total_gets, rank)
            VALUES (?, 0, 0)
            """,
            [user.id],
        )
