__all__ = ["GAME_INFO", "LEADERBOARD_MEDALS"]

COLORS = {"magenta", "red", "orange", "gold", "green", "teal", "blue", "purple"}

GAME_INFO = (
    "To earn a GET, send a message directly after a build notification is "
    "posted. (This only works in the same channel as the notification.) "
    "This means that it is a race to see who can post a message first after a "
    "new Discord build gets deployed.\n\n"
    "If there are multiple unclaimed build notifications, they stack up and "
    "can all be claimed in one fell swoop.\n\n"
    "To see your total amount of GETs, type `{prefix}gets profile`, or "
    "`{prefix}g profile` for short. "
    "You can also use this command to view other people's profiles. "
    "To see a leaderboard of GET earners, type `{prefix}g top`."
)

LEADERBOARD_MEDALS = [
    "\N{FIRST PLACE MEDAL}",
    "\N{SECOND PLACE MEDAL}",
    "\N{THIRD PLACE MEDAL}",
]
