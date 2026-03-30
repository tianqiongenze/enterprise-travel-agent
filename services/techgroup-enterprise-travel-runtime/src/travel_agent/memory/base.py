"""Module provides memory backends and access helpers."""

from typing import List


class MemoryStore:
    def append_message(self, key: str, message: str) -> None:
        raise NotImplementedError

    def read_messages(self, key: str, limit: int = 50) -> List[str]:
        raise NotImplementedError

    def query_messages(self, key: str, query: str, limit: int = 10) -> List[str]:
        del query
        return self.read_messages(key, limit=limit)
