__all__ = ["BLOCK", "ALLOW", "HUSH_PERMS", "HUSH", "NEUTRAL_HUSH_PERMS"]

from typing import Dict

from discord import PermissionOverwrite

BLOCK = PermissionOverwrite(read_messages=False)
ALLOW = PermissionOverwrite(read_messages=True)
HUSH_PERMS: Dict[str, bool] = {"add_reactions": False, "send_messages": False}
HUSH = PermissionOverwrite(**HUSH_PERMS)
NEUTRAL_HUSH_PERMS = {key: None for key in HUSH_PERMS}
