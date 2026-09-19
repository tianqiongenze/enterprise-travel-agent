"""Per-request execution budget for agent steps and tool calls.

The gateway-facing controls (maxAgentSteps / maxToolCalls) are enforced here at
execution time, not merely validated: the MCP registry consumes a tool-call
budget item on every tool invocation and the orchestration engines consume an
agent-step item on every pipeline stage. Exhaustion raises BudgetExceeded,
which surfaces as a 4xx-class failure upstream instead of an unbounded run.
"""

from __future__ import annotations

import os
from contextvars import ContextVar
from typing import Dict, Optional

_current_budget: ContextVar[Optional["ExecutionBudget"]] = ContextVar(
    "travel_execution_budget", default=None
)


class BudgetExceeded(RuntimeError):
    """Raised when the request exhausts its agent-step or tool-call budget."""


class ExecutionBudget:
    def __init__(self, max_agent_steps: Optional[int] = None, max_tool_calls: Optional[int] = None) -> None:
        self.max_agent_steps = max_agent_steps
        self.max_tool_calls = max_tool_calls
        self.used_agent_steps = 0
        self.used_tool_calls = 0

    def consume_agent_step(self, step_name: str) -> None:
        self.used_agent_steps += 1
        if self.max_agent_steps is not None and self.used_agent_steps > self.max_agent_steps:
            raise BudgetExceeded(
                f"agent step budget exhausted at step '{step_name}' "
                f"({self.used_agent_steps - 1}/{self.max_agent_steps} used)"
            )

    def consume_tool_call(self, tool_name: str) -> None:
        self.used_tool_calls += 1
        if self.max_tool_calls is not None and self.used_tool_calls > self.max_tool_calls:
            raise BudgetExceeded(
                f"tool call budget exhausted at tool '{tool_name}' "
                f"({self.used_tool_calls - 1}/{self.max_tool_calls} used)"
            )

    def snapshot(self) -> Dict[str, Optional[int]]:
        return {
            "max_agent_steps": self.max_agent_steps,
            "max_tool_calls": self.max_tool_calls,
            "used_agent_steps": self.used_agent_steps,
            "used_tool_calls": self.used_tool_calls,
        }


def set_current_budget(budget: Optional[ExecutionBudget]) -> object:
    """Install the per-request budget into the ambient context."""
    return _current_budget.set(budget)


def reset_current_budget(token: object) -> None:
    _current_budget.reset(token)  # type: ignore[arg-type]


def current_budget() -> Optional["ExecutionBudget"]:
    return _current_budget.get()


def budget_from_env_defaults() -> Optional[ExecutionBudget]:
    """Unlimited budget unless ambient defaults are configured."""
    steps = os.getenv("TRAVEL_DEFAULT_MAX_AGENT_STEPS", "").strip()
    calls = os.getenv("TRAVEL_DEFAULT_MAX_TOOL_CALLS", "").strip()
    if not steps and not calls:
        return None
    return ExecutionBudget(
        max_agent_steps=int(steps) if steps else None,
        max_tool_calls=int(calls) if calls else None,
    )
