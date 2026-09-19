"""MCP tool registry with audit logging and per-request tool-call budgets."""

import time
import os
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from ..orchestration.budget import current_budget

if TYPE_CHECKING:
    from ..discovery.base import ServiceRegistry


class MCPToolRegistry:
    def __init__(self, service_registry: Optional["ServiceRegistry"] = None) -> None:
        self._tools: Dict[str, Callable[..., Any]] = {}
        self.audit_logs: List[Dict[str, Any]] = []
        self.service_registry = service_registry
        self.max_audit_logs = int(os.getenv("TRAVEL_MCP_AUDIT_MAX_RECORDS", "500"))

    def register(self, name: str, func: Callable[..., Any]) -> None:
        self._tools[name] = func
        if self.service_registry is not None:
            self.service_registry.register_tool(name, "mcp://tool/%s" % name)

    def list_tools(self) -> List[str]:
        return sorted(self._tools.keys())

    def call(self, name: str, **kwargs: Any) -> Any:
        return self._call_internal(name, context=None, event="call", **kwargs)

    def call_with_context(self, name: str, context: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Any:
        return self._call_internal(name, context=context or {}, event="call_with_context", **kwargs)

    def _call_internal(
        self,
        name: str,
        context: Optional[Dict[str, Any]],
        event: str,
        **kwargs: Any,
    ) -> Any:
        if name not in self._tools:
            raise ValueError("Tool not found: %s" % name)
        budget = current_budget()
        if budget is not None:
            budget.consume_tool_call(name)
        started = time.time()
        result = self._tools[name](**kwargs)
        elapsed_ms = int((time.time() - started) * 1000)
        self.audit_logs.append(
            {
                "tool": name,
                "kwargs": kwargs,
                "context": context or {},
                "event": event,
                "latency_ms": elapsed_ms,
                "result_count": len(result) if isinstance(result, list) else 1,
            }
        )
        overflow = len(self.audit_logs) - self.max_audit_logs
        if overflow > 0:
            del self.audit_logs[:overflow]
        return result

