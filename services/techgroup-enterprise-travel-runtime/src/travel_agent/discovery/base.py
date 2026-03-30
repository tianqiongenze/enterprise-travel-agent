"""Module provides service components and helpers."""

from typing import Dict, List


class ServiceRegistry:
    def register(self, service_name: str, endpoint: str) -> None:
        raise NotImplementedError

    def discover(self, service_name: str) -> str:
        raise NotImplementedError

    def list_services(self) -> List[str]:
        raise NotImplementedError

    def register_tool(self, tool_name: str, endpoint: str) -> None:
        raise NotImplementedError

    def list_tools(self) -> Dict[str, str]:
        raise NotImplementedError

    def close(self) -> None:
        return
