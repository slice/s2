__all__ = ["STATEMENTS"]

STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS voyager_gets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id BIGINT,
        get_message_id BIGINT,
        voyager_message_id BIGINT,
        channel_id BIGINT,
        guild_id BIGINT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS voyager_stats (
        user_id BIGINT PRIMARY KEY,
        total_gets INTEGER,
        rank INTEGER,
        last_get TIMESTAMP
    )
    """,
]
