"""Module defines API handlers."""

from dataclasses import dataclass
from typing import List


@dataclass
class RuntimeInvokeRequest:
    tenantId: str
    userId: str
    policyId: str
    conversationId: str
    idempotencyKey: str
    city: str
    days: int
    budget: float
    travelers: int
    preferences: List[str]
    maxAgentSteps: int
    maxToolCalls: int
    allowedTools: List[str]
