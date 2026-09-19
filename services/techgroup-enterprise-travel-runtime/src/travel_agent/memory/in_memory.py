"""Module provides memory backends and access helpers."""

from typing import Dict, List

from .base import MemoryStore


class InMemoryStore(MemoryStore):
    def __init__(self) -> None:
        self._rows: Dict[str, List[str]] = {}
        self._max_per_key = 200

    def append_message(self, key: str, message: str) -> None:
        rows = self._rows.setdefault(key, [])
        rows.append(message)
        overflow = len(rows) - self._max_per_key
        if overflow > 0:
            del rows[:overflow]

    def read_messages(self, key: str, limit: int = 50) -> List[str]:
        rows = self._rows.get(key, [])
        return rows[-limit:]
