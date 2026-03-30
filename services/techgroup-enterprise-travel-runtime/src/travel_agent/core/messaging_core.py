"""Module provides service components and helpers."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict


class DeliverySemantics(str, Enum):
    """Cross-runtime delivery contract labels used by A2A and event consumers."""

    AT_LEAST_ONCE = "at-least-once"
    EFFECTIVELY_ONCE = "effectively-once"


@dataclass(frozen=True)
class MessageRetryPolicy:
    """Shared retry knobs to keep Python/Java/Go defaults aligned."""

    max_retries: int = 3
    backoff_ms: int = 200
    pending_retry_idle_ms: int = 10000


@dataclass(frozen=True)
class MessageEnvelope:
    """Canonical envelope for traceability and idempotent replay decisions."""

    topic: str
    payload: Dict[str, object]
    trace_id: str = ""
    idempotency_key: str = ""
    semantics: DeliverySemantics = DeliverySemantics.AT_LEAST_ONCE
    metadata: Dict[str, object] = field(default_factory=dict)
