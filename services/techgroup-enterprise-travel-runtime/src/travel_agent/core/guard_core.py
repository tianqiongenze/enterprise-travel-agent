"""Module provides service components and helpers."""

from dataclasses import dataclass


@dataclass(frozen=True)
class GuardDecision:
    """Canonical decision shape shared by gateway/runtime guard implementations."""

    allow: bool
    reason: str


@dataclass(frozen=True)
class GuardMetrics:
    """Stable metric names so dashboards remain language-agnostic."""

    rate_limited_total: str = "travel_guard_rate_limited_total"
    duplicate_submission_total: str = "travel_guard_duplicate_submission_total"
    circuit_open_total: str = "travel_guard_circuit_open_total"


class GuardRuntime:
    """Unified guard runtime contract for rate-limit/idempotency/circuit modules."""

    def allow_request(self, scope: str) -> GuardDecision:
        """Return deny when request volume for the caller scope exceeds budget."""
        raise NotImplementedError

    def claim_idempotency(self, tenant_id: str, idem_key: str) -> GuardDecision:
        """Return deny when the idempotency key was already consumed in this tenant."""
        raise NotImplementedError

    def allow_circuit(self, circuit_name: str) -> GuardDecision:
        """Return deny while downstream circuit stays in open state."""
        raise NotImplementedError
