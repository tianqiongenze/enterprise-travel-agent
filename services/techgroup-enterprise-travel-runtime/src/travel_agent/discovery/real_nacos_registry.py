"""Module provides service components and helpers."""

import logging
import os

logger = logging.getLogger("travel_agent.discovery.nacos")
import threading
import time
import json
from typing import Dict, List, Optional, Any, cast

try:
    import requests
except Exception:
    requests = None

from .base import ServiceRegistry


class RealNacosRegistry(ServiceRegistry):
    def __init__(self) -> None:
        self.server = os.getenv("NACOS_SERVER_ADDR", "")
        self.namespace = os.getenv("NACOS_NAMESPACE", "public")
        self.group = os.getenv("NACOS_GROUP", "DEFAULT_GROUP")
        self.username = os.getenv("NACOS_USERNAME", "")
        self.password = os.getenv("NACOS_PASSWORD", "")
        self.cluster = os.getenv("NACOS_CLUSTER", "DEFAULT")
        self.enabled = bool(self.server and requests is not None)
        self._registered: Dict[str, Dict[str, str]] = {}
        self._tools_cache: Dict[str, str] = {}
        self._stop = False
        self._beat_thread: Optional[threading.Thread] = None
        self._session = requests.Session() if requests is not None else None
        self._access_token: Optional[str] = None
        self._token_expire_at: float = 0.0
        self._tool_runtime_endpoint = os.getenv("TRAVEL_RUNTIME_ENDPOINT", "http://127.0.0.1:8000")
        self._cache_backend = os.getenv("TRAVEL_REGISTRY_CACHE_BACKEND", "python").strip().lower()
        self._cache_url = os.getenv("TRAVEL_REGISTRY_CACHE_URL", "http://localhost:8093").rstrip("/")
        if self.enabled:
            self._start_heartbeat_loop()

    def register(self, service_name: str, endpoint: str) -> None:
        if not self.enabled:
            self._registered[service_name] = {"endpoint": endpoint}
            return
        if self._session is None:
            raise RuntimeError("requests session unavailable")
        session = cast(Any, self._session)
        params = self._auth_params()
        host, port = _parse_endpoint(endpoint)
        data = {
            "serviceName": service_name,
            "ip": host,
            "port": str(port),
            "namespaceId": self.namespace,
            "groupName": self.group,
            "clusterName": self.cluster,
            "ephemeral": "true",
            "metadata": '{"endpoint":"%s"}' % endpoint,
        }
        auth = _auth_tuple(self.username, self.password)
        try:
            response = session.post(self.server.rstrip("/") + "/nacos/v1/ns/instance", params=params, data=data, auth=auth, timeout=3)
            response.raise_for_status()
        except Exception as error:
            # An unreachable registry must not prevent boot: degrade to the
            # local registry view unless the operator demanded fail-fast.
            if os.getenv("TRAVEL_REGISTRY_FAIL_FAST", "false").strip().lower() == "true":
                raise
            logger.warning("nacos register %s failed (%s); degrading to local registry view", service_name, error)
        self._registered[service_name] = {"endpoint": endpoint, "ip": host, "port": str(port)}

    def discover(self, service_name: str) -> str:
        if not self.enabled:
            if service_name not in self._registered:
                raise ValueError("Service not found: %s" % service_name)
            return self._registered[service_name]["endpoint"]
        if self._session is None:
            raise RuntimeError("requests session unavailable")
        session = cast(Any, self._session)
        params = self._auth_params()
        params = {
            "serviceName": service_name,
            "namespaceId": self.namespace,
            "groupName": self.group,
            "healthyOnly": "true",
        }
        params.update(self._auth_params())
        auth = _auth_tuple(self.username, self.password)
        response = session.get(self.server.rstrip("/") + "/nacos/v1/ns/instance/list", params=params, auth=auth, timeout=3)
        response.raise_for_status()
        payload = response.json()
        hosts = payload.get("hosts", [])
        if not hosts:
            raise ValueError("Service not found in Nacos: %s" % service_name)
        host = hosts[0]
        metadata = host.get("metadata", {})
        endpoint = metadata.get("endpoint")
        if endpoint:
            return endpoint
        return "http://%s:%s" % (host.get("ip"), host.get("port"))

    def list_services(self) -> List[str]:
        if not self.enabled:
            return sorted(self._registered.keys())
        if self._session is None:
            raise RuntimeError("requests session unavailable")
        session = cast(Any, self._session)
        params = {"namespaceId": self.namespace, "groupName": self.group, "pageNo": "1", "pageSize": "500"}
        params.update(self._auth_params())
        auth = _auth_tuple(self.username, self.password)
        response = session.get(self.server.rstrip("/") + "/nacos/v1/ns/service/list", params=params, auth=auth, timeout=3)
        response.raise_for_status()
        payload = response.json()
        names = payload.get("doms", [])
        return sorted([_strip_group(name) for name in names])

    def register_tool(self, tool_name: str, endpoint: str) -> None:
        self._tools_cache[tool_name] = endpoint
        if not self.enabled:
            return
        tool_service = "mcp-tool-" + tool_name
        self.register(tool_service, self._tool_runtime_endpoint)

    def list_tools(self) -> Dict[str, str]:
        cached = self._cache_get("nacos:tools")
        if cached is not None:
            return cached
        if not self.enabled:
            return dict(self._tools_cache)
        if self._session is None:
            return dict(self._tools_cache)
        session = cast(Any, self._session)
        params = {"namespaceId": self.namespace, "groupName": self.group, "pageNo": "1", "pageSize": "1000"}
        params.update(self._auth_params())
        auth = _auth_tuple(self.username, self.password)
        response = session.get(self.server.rstrip("/") + "/nacos/v1/ns/service/list", params=params, auth=auth, timeout=3)
        response.raise_for_status()
        payload = response.json()
        names = payload.get("doms", [])
        rows = dict(self._tools_cache)
        for name in names:
            clean_name = _strip_group(name)
            if clean_name.startswith("mcp-tool-"):
                tool_name = clean_name.replace("mcp-tool-", "", 1)
                if tool_name not in rows:
                    rows[tool_name] = "mcp://tool/" + tool_name
        self._cache_set("nacos:tools", rows)
        return rows

    def close(self) -> None:
        self._stop = True
        if self._beat_thread is not None and self._beat_thread.is_alive():
            self._beat_thread.join(timeout=1)

    def _start_heartbeat_loop(self) -> None:
        self._beat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._beat_thread.start()

    def _heartbeat_loop(self) -> None:
        while not self._stop:
            if self.enabled:
                for service_name, node in list(self._registered.items()):
                    try:
                        self._send_heartbeat(service_name, node["ip"], int(node["port"]))
                    except Exception:
                        pass
            time.sleep(5)

    def _send_heartbeat(self, service_name: str, host: str, port: int) -> None:
        if self._session is None:
            return
        session = cast(Any, self._session)
        beat = '{"serviceName":"%s","ip":"%s","port":%s,"cluster":"%s"}' % (service_name, host, port, self.cluster)
        data = {
            "serviceName": service_name,
            "namespaceId": self.namespace,
            "groupName": self.group,
            "beat": beat,
        }
        params = self._auth_params()
        auth = _auth_tuple(self.username, self.password)
        session.put(self.server.rstrip("/") + "/nacos/v1/ns/instance/beat", params=params, data=data, auth=auth, timeout=3)

    def _auth_params(self) -> Dict[str, str]:
        token = self._ensure_access_token()
        if token:
            return {"accessToken": token}
        return {}

    def _ensure_access_token(self) -> Optional[str]:
        if not self.username or not self.password:
            return None
        now = time.time()
        if self._access_token and now < self._token_expire_at:
            return self._access_token
        if self._session is None:
            return None
        session = cast(Any, self._session)
        login_paths = ["/nacos/v1/auth/users/login", "/nacos/v1/auth/login"]
        for path in login_paths:
            try:
                response = session.post(
                    self.server.rstrip("/") + path,
                    data={"username": self.username, "password": self.password},
                    timeout=3,
                )
                if response.status_code >= 200 and response.status_code < 300:
                    payload = response.json()
                    token = payload.get("accessToken") or payload.get("token")
                    if token:
                        ttl = int(payload.get("tokenTtl", 18000))
                        self._access_token = token
                        self._token_expire_at = time.time() + max(30, ttl - 30)
                        return token
            except Exception:
                continue
        return None

    def _cache_get(self, key: str) -> Optional[Dict[str, str]]:
        if self._cache_backend != "go":
            return None
        if self._session is None:
            return None
        try:
            response = self._session.get(self._cache_url + "/v1/cache/get/" + key, timeout=1)
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
        if self._session is None:
            return
        try:
            self._session.post(
                self._cache_url + "/v1/cache/set",
                json={"key": key, "value": json.dumps(value), "ttlSeconds": 15},
                timeout=1,
            )
        except Exception:
            pass


def _parse_endpoint(endpoint: str) -> tuple:
    # Endpoints may carry a path (e.g. "http://host:8000/agent/manager");
    # only the host:port part identifies the service instance.
    from urllib.parse import urlparse

    if "//" not in endpoint:
        endpoint = "http://" + endpoint
    parsed = urlparse(endpoint)
    host = parsed.hostname or ""
    if not host:
        raise ValueError(f"invalid service endpoint: {endpoint!r}")
    if parsed.port:
        return host, int(parsed.port)
    return host, 443 if parsed.scheme == "https" else 80


def _auth_tuple(username: str, password: str):
    if username and password:
        return username, password
    return None


def _strip_group(name: str) -> str:
    if "@@" in name:
        return name.split("@@", 1)[1]
    return name
