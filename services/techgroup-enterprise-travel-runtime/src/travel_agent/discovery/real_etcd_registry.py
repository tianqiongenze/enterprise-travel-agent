"""Module provides service components and helpers."""

import os
import threading
import time
import json
from importlib import import_module, util
from typing import Dict, List, Optional, Any, cast

etcd_module = None
if util.find_spec("etcd3") is not None:
    etcd_module = import_module("etcd3")

from .base import ServiceRegistry


class RealEtcdRegistry(ServiceRegistry):
    def __init__(self) -> None:
        self.host = os.getenv("ETCD_HOST", "")
        self.port = int(os.getenv("ETCD_PORT", "2379"))
        self.prefix = os.getenv("ETCD_PREFIX", "/travel-agent")
        self.ttl = int(os.getenv("ETCD_LEASE_TTL", "15"))
        self.client_mode = os.getenv("TRAVEL_ETCD_CLIENT_MODE", "auto").strip().lower()
        if self.client_mode not in {"legacy", "new", "auto"}:
            raise RuntimeError("Unsupported TRAVEL_ETCD_CLIENT_MODE: %s" % self.client_mode)
        self._selected_mode = self._resolve_mode()
        self.enabled = bool(self.host and self._selected_mode in {"legacy", "new"})
        self._client: Optional[object] = None
        self._lease: Optional[object] = None
        self._registered_services: Dict[str, str] = {}
        self._registered_tools: Dict[str, str] = {}
        self._cache_backend = os.getenv("TRAVEL_REGISTRY_CACHE_BACKEND", "python").strip().lower()
        self._cache_url = os.getenv("TRAVEL_REGISTRY_CACHE_URL", "http://localhost:8093").rstrip("/")
        self._stop = False
        self._keepalive_thread: Optional[threading.Thread] = None
        if self.enabled:
            try:
                if self._selected_mode == "legacy":
                    if not _supports_legacy_client(etcd_module):
                        raise RuntimeError("legacy etcd3 module unavailable")
                    etcd3_client_module = cast(Any, etcd_module)
                    self._client = etcd3_client_module.client(host=self.host, port=self.port, timeout=3)
                    client = cast(Any, self._client)
                    self._lease = client.lease(self.ttl)
                else:
                    if not _supports_new_client(etcd_module):
                        raise RuntimeError("new etcd3-py module unavailable")
                    etcd3_client_module = cast(Any, etcd_module)
                    self._client = etcd3_client_module.Client(host=self.host, port=self.port)
            except Exception as error:
                print(f"[registry-etcd] init failed, fallback local: {error}")
                self.enabled = False
                self._client = None
                self._lease = None
            if self.enabled:
                self._keepalive_thread = threading.Thread(target=self._keepalive_loop, daemon=True)
                self._keepalive_thread.start()

    def register(self, service_name: str, endpoint: str) -> None:
        self._registered_services[service_name] = endpoint
        if not self.enabled:
            return
        if self._client is None:
            raise RuntimeError("etcd client unavailable")
        client = cast(Any, self._client)
        key = self._service_key(service_name)
        if self._selected_mode == "legacy":
            client.put(key, endpoint, lease=self._lease)
        else:
            client.put(key, endpoint)

    def discover(self, service_name: str) -> str:
        if not self.enabled:
            if service_name not in self._registered_services:
                raise ValueError("Service not found: %s" % service_name)
            return self._registered_services[service_name]
        if self._client is None:
            raise RuntimeError("etcd client unavailable")
        client = cast(Any, self._client)
        if self._selected_mode == "legacy":
            value, _ = client.get(self._service_key(service_name))
        else:
            response = client.range(self._service_key(service_name))
            kvs = getattr(response, "kvs", [])
            value = kvs[0].value if kvs else None
        if value is None:
            raise ValueError("Service not found in Etcd: %s" % service_name)
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return str(value)

    def list_services(self) -> List[str]:
        if not self.enabled:
            return sorted(self._registered_services.keys())
        if self._client is None:
            raise RuntimeError("etcd client unavailable")
        client = cast(Any, self._client)
        services: List[str] = []
        if self._selected_mode == "legacy":
            for _, meta in client.get_prefix(self.prefix + "/services/"):
                key = meta.key.decode("utf-8")
                services.append(key.rsplit("/", 1)[-1])
        else:
            response = client.range(self.prefix + "/services/", range_end=self.prefix + "/services0")
            for kv in getattr(response, "kvs", []):
                key = kv.key.decode("utf-8") if isinstance(kv.key, bytes) else str(kv.key)
                services.append(key.rsplit("/", 1)[-1])
        return sorted(services)

    def register_tool(self, tool_name: str, endpoint: str) -> None:
        self._registered_tools[tool_name] = endpoint
        if not self.enabled:
            return
        if self._client is None:
            raise RuntimeError("etcd client unavailable")
        client = cast(Any, self._client)
        key = self._tool_key(tool_name)
        if self._selected_mode == "legacy":
            client.put(key, endpoint, lease=self._lease)
        else:
            client.put(key, endpoint)

    def list_tools(self) -> Dict[str, str]:
        cached = self._cache_get("etcd:tools")
        if cached is not None:
            return cached
        if not self.enabled:
            return dict(self._registered_tools)
        if self._client is None:
            raise RuntimeError("etcd client unavailable")
        client = cast(Any, self._client)
        rows: Dict[str, str] = {}
        if self._selected_mode == "legacy":
            for value, meta in client.get_prefix(self.prefix + "/tools/"):
                key = meta.key.decode("utf-8")
                name = key.rsplit("/", 1)[-1]
                rows[name] = value.decode("utf-8")
        else:
            response = client.range(self.prefix + "/tools/", range_end=self.prefix + "/tools0")
            for kv in getattr(response, "kvs", []):
                key = kv.key.decode("utf-8") if isinstance(kv.key, bytes) else str(kv.key)
                name = key.rsplit("/", 1)[-1]
                value = kv.value.decode("utf-8") if isinstance(kv.value, bytes) else str(kv.value)
                rows[name] = value
        self._cache_set("etcd:tools", rows)
        return rows

    def close(self) -> None:
        self._stop = True
        if self._keepalive_thread is not None and self._keepalive_thread.is_alive():
            self._keepalive_thread.join(timeout=1)
        if self._client is not None:
            client = cast(Any, self._client)
            client.close()

    def _service_key(self, service_name: str) -> str:
        return self.prefix + "/services/" + service_name

    def _tool_key(self, tool_name: str) -> str:
        return self.prefix + "/tools/" + tool_name

    def _keepalive_loop(self) -> None:
        while not self._stop:
            try:
                if self._selected_mode == "legacy" and self._lease is not None:
                    lease = cast(Any, self._lease)
                    lease.refresh()
            except Exception:
                pass
            time.sleep(max(1, self.ttl // 3))

    def _resolve_mode(self) -> str:
        if self.client_mode == "legacy":
            if not _supports_legacy_client(etcd_module):
                raise RuntimeError("TRAVEL_ETCD_CLIENT_MODE=legacy requires python-etcd3 compatible module")
            return "legacy"
        if self.client_mode == "new":
            if not _supports_new_client(etcd_module):
                raise RuntimeError("TRAVEL_ETCD_CLIENT_MODE=new requires etcd3-py compatible module")
            return "new"
        if _supports_legacy_client(etcd_module):
            return "legacy"
        if _supports_new_client(etcd_module):
            return "new"
        return ""

    def _cache_get(self, key: str) -> Optional[Dict[str, str]]:
        if self._cache_backend != "go":
            return None
        if self._client is None:
            return None
        try:
            import requests

            response = requests.get(self._cache_url + "/v1/cache/get/" + key, timeout=1)
            if response.status_code != 200:
                return None
            payload = response.json()
            value = payload.get("value")
            if not value:
                return None
            return json.loads(value)
        except Exception:
            return None

    def _cache_set(self, key: str, value: Dict[str, str]) -> None:
        if self._cache_backend != "go":
            return
        try:
            import requests

            requests.post(
                self._cache_url + "/v1/cache/set",
                json={"key": key, "value": json.dumps(value), "ttlSeconds": 15},
                timeout=1,
            )
        except Exception:
            pass


def _supports_legacy_client(module: Any) -> bool:
    if module is None or not hasattr(module, "client"):
        return False
    return callable(getattr(module, "client"))


def _supports_new_client(module: Any) -> bool:
    return module is not None and hasattr(module, "Client")
