__all__ = ["STATEMENTS"]

STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS voyager_gets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id BIGINT NOT NULL,
        get_message_id BIGINT NOT NULL,
        voyager_message_id BIGINT NOT NULL,
        channel_id BIGINT NOT NULL,
        guild_id BIGINT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS voyager_stats (
        user_id BIGINT PRIMARY KEY,
        total_gets INTEGER NOT NULL,
        rank INTEGER NOT NULL,
        last_get TIMESTAMP NOT NULL
    )
    """,
]
