"""Module exposes tool helpers and adapters."""

import json
import os
from typing import Any, Dict, List


class DataStore:
    def __init__(self, data_dir: str) -> None:
        self.data_dir = data_dir

    def _read(self, filename: str) -> List[Dict[str, Any]]:
        path = os.path.join(self.data_dir, filename)
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)

    def hotels(self) -> List[Dict[str, Any]]:
        return self._read("hotels.json")

    def transports(self) -> List[Dict[str, Any]]:
        return self._read("transports.json")

    def attractions(self) -> List[Dict[str, Any]]:
        return self._read("attractions.json")

    def foods(self) -> List[Dict[str, Any]]:
        return self._read("foods.json")

    def events(self) -> List[Dict[str, Any]]:
        return self._read("events.json")

