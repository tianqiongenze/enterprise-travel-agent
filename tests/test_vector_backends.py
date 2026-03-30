"""Module provides service components and helpers."""

import os
import unittest
from unittest.mock import patch

from src.travel_agent.memory.vector_store import VectorMemoryStore


class VectorBackendTestCase(unittest.TestCase):
    def test_local_backend_query(self) -> None:
        previous_backend = os.environ.get("TRAVEL_VECTOR_BACKEND")
        os.environ["TRAVEL_VECTOR_BACKEND"] = "local"

        store = VectorMemoryStore()
        key = "tenant:user:conv"
        store.append_message(key, '{"city":"上海","type":"request"}')
        store.append_message(key, '{"city":"北京","type":"request"}')
        hits = store.query_messages(key, "上海", limit=2)
        self.assertTrue(len(hits) >= 1)

        if previous_backend is None:
            del os.environ["TRAVEL_VECTOR_BACKEND"]
        else:
            os.environ["TRAVEL_VECTOR_BACKEND"] = previous_backend

    def test_unknown_backend_falls_back_when_not_strict(self) -> None:
        previous_backend = os.environ.get("TRAVEL_VECTOR_BACKEND")
        previous_strict = os.environ.get("TRAVEL_VECTOR_STRICT")

        os.environ["TRAVEL_VECTOR_BACKEND"] = "unknown-backend"
        os.environ["TRAVEL_VECTOR_STRICT"] = "false"

        store = VectorMemoryStore()
        self.assertEqual(store.backend_name, "local")

        if previous_backend is None:
            del os.environ["TRAVEL_VECTOR_BACKEND"]
        else:
            os.environ["TRAVEL_VECTOR_BACKEND"] = previous_backend

        if previous_strict is None:
            del os.environ["TRAVEL_VECTOR_STRICT"]
        else:
            os.environ["TRAVEL_VECTOR_STRICT"] = previous_strict

    def test_faiss_backend_falls_back_when_not_strict(self) -> None:
        previous_backend = os.environ.get("TRAVEL_VECTOR_BACKEND")
        previous_strict = os.environ.get("TRAVEL_VECTOR_STRICT")
        os.environ["TRAVEL_VECTOR_BACKEND"] = "faiss"
        os.environ["TRAVEL_VECTOR_STRICT"] = "false"

        import importlib as raw_importlib

        original_import = raw_importlib.import_module

        def fake_import(name: str):
            if name == "faiss":
                raise ImportError("faiss not installed")
            return original_import(name)

        with patch("importlib.import_module", side_effect=fake_import):
            store = VectorMemoryStore()
            self.assertEqual(store.backend_name, "local")

        if previous_backend is None:
            del os.environ["TRAVEL_VECTOR_BACKEND"]
        else:
            os.environ["TRAVEL_VECTOR_BACKEND"] = previous_backend
        if previous_strict is None:
            del os.environ["TRAVEL_VECTOR_STRICT"]
        else:
            os.environ["TRAVEL_VECTOR_STRICT"] = previous_strict


if __name__ == "__main__":
    unittest.main()

