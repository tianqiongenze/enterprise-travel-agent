"""Module provides memory backends and access helpers."""

from typing import Dict, List

from .base import MemoryStore


class InMemoryStore(MemoryStore):
    def __init__(self) -> None:
        self._rows: Dict[str, List[str]] = {}

    def append_message(self, key: str, message: str) -> None:
        self._rows.setdefault(key, []).append(message)

    def read_messages(self, key: str, limit: int = 50) -> List[str]:
        rows = self._rows.get(key, [])
        return rows[-limit:]
