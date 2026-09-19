"""Module exposes tool helpers and adapters."""

import json
import os
from typing import Any, Dict, List


class DataStore:
    def __init__(self, data_dir: str) -> None:
        self.data_dir = data_dir
        self._cache: Dict[str, List[Dict[str, Any]]] = {}
        self._index_by_city: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}

    def _read(self, filename: str) -> List[Dict[str, Any]]:
        cached = self._cache.get(filename)
        if cached is not None:
            return cached
        path = os.path.join(self.data_dir, filename)
        with open(path, "r", encoding="utf-8") as file:
            rows = json.load(file)
        self._cache[filename] = rows
        return rows

    def _index_city(self, filename: str) -> Dict[str, List[Dict[str, Any]]]:
        indexed = self._index_by_city.get(filename)
        if indexed is not None:
            return indexed
        index: Dict[str, List[Dict[str, Any]]] = {}
        for row in self._read(filename):
            city = str(row.get("city", ""))
            index.setdefault(city, []).append(row)
        self._index_by_city[filename] = index
        return index

    def hotels_by_city(self, city: str) -> List[Dict[str, Any]]:
        return self._index_city("hotels.json").get(city, [])

    def transports_by_city(self, city: str) -> List[Dict[str, Any]]:
        return self._index_city("transports.json").get(city, [])

    def attractions_by_city(self, city: str) -> List[Dict[str, Any]]:
        return self._index_city("attractions.json").get(city, [])

    def foods_by_city(self, city: str) -> List[Dict[str, Any]]:
        return self._index_city("foods.json").get(city, [])

    def events_by_city(self, city: str) -> List[Dict[str, Any]]:
        return self._index_city("events.json").get(city, [])

    def activities_by_city(self, city: str) -> List[Dict[str, Any]]:
        return self._index_city("activities.json").get(city, [])

    def souvenirs_by_city(self, city: str) -> List[Dict[str, Any]]:
        return self._index_city("souvenirs.json").get(city, [])

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

    def activities(self) -> List[Dict[str, Any]]:
        return self._read("activities.json")

    def souvenirs(self) -> List[Dict[str, Any]]:
        return self._read("souvenirs.json")

