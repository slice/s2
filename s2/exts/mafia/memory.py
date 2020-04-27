__all__ = ["Memory", "Key"]

from typing import Any, Dict, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from .player import Player


class Key:
    def __init__(self, key: str, *, persistent: bool = False):
        self.key = key
        self.persistent = persistent

    @classmethod
    def player(cls, key: str, player: "Player") -> "Key":
        """Create a player-local key."""
        return Key(key).localized(str(player.id))

    @classmethod
    def role(cls, key: str, player: "Player") -> "Key":
        """Create a key for a player's role."""
        return cls(key) if player.role.grouped else cls.player(key, player)

    def localized(self, id: Union["Player", str]) -> "Key":
        """Copy and localize a key."""
        from .player import Player

        if isinstance(id, Player):
            id = str(id.id)
        return Key(f"{self.key}_{id}", persistent=self.persistent)

    def __hash__(self) -> int:
        return hash((self.key, self.persistent))

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Key):
            return NotImplemented
        return self.key == other.key and self.persistent == other.persistent

    def __str__(self) -> str:
        return self.key

    def __repr__(self) -> str:
        return f"Key({self.key!r}, persistent={self.persistent!r})"


class Memory(Dict[Key, Any]):
    """A mapping used to keep track of player actions."""

    def reset(self) -> None:
        for key in list(self.keys()):
            if not key.persistent:
                del self[key]
