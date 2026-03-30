"""Module provides service components and helpers."""

from typing import Dict, List

from .base import ServiceRegistry


class EtcdStyleRegistry(ServiceRegistry):
    def __init__(self) -> None:
        self._kv_services: Dict[str, str] = {}
        self._kv_tools: Dict[str, str] = {}

    def register(self, service_name: str, endpoint: str) -> None:
        self._kv_services[service_name] = endpoint

    def discover(self, service_name: str) -> str:
        if service_name not in self._kv_services:
            raise ValueError("Service not found: %s" % service_name)
        return self._kv_services[service_name]

    def list_services(self) -> List[str]:
        return sorted(self._kv_services.keys())

    def register_tool(self, tool_name: str, endpoint: str) -> None:
        self._kv_tools[tool_name] = endpoint

    def list_tools(self) -> Dict[str, str]:
        return dict(self._kv_tools)
