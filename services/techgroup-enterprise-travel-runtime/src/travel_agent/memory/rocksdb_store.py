"""Module provides memory backends and access helpers."""

import importlib
import os
from typing import Any, List, Optional

from .base import MemoryStore


class RocksDBMemoryStore(MemoryStore):
    def __init__(self) -> None:
        self.db_path = os.getenv("TRAVEL_ROCKSDB_PATH", "")
        if not self.db_path:
            raise RuntimeError("TRAVEL_MEMORY_BACKEND=rocksdb requires TRAVEL_ROCKSDB_PATH")
        rocksdb_module = _require_rocksdb_module()
        options = rocksdb_module.Options()
        options.create_if_missing = True
        self._db: Optional[Any] = rocksdb_module.DB(self.db_path, options)
        self.enabled = True

    def append_message(self, key: str, message: str) -> None:
        if not self.enabled or self._db is None:
            return
        count_key = (key + "::__count").encode("utf-8")
        count_bytes = self._db.get(count_key)
        if count_bytes is None:
            count = 0
        else:
            count = int(count_bytes.decode("utf-8"))
        row_key = (key + "::%09d" % count).encode("utf-8")
        self._db.put(row_key, message.encode("utf-8"))
        self._db.put(count_key, str(count + 1).encode("utf-8"))

    def read_messages(self, key: str, limit: int = 50) -> List[str]:
        if not self.enabled or self._db is None:
            return []
        count_key = (key + "::__count").encode("utf-8")
        count_bytes = self._db.get(count_key)
        if count_bytes is None:
            return []
        count = int(count_bytes.decode("utf-8"))
        start = max(0, count - limit)
        rows: List[str] = []
        for index in range(start, count):
            row_key = (key + "::%09d" % index).encode("utf-8")
            value = self._db.get(row_key)
            if value is not None:
                rows.append(value.decode("utf-8"))
        return rows


def _require_rocksdb_module() -> Any:
    try:
        return importlib.import_module("rocksdb")
    except ImportError as error:
        raise RuntimeError(
            "TRAVEL_MEMORY_BACKEND=rocksdb requires python-rocksdb and TRAVEL_ROCKSDB_PATH"
        ) from error
