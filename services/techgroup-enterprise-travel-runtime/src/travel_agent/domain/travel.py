"""Travel domain model: value objects, aggregate root, domain events, ports.

This is the domain layer in DDD terms — no infrastructure imports, no I/O.
The aggregate root (:class:`TripPlan`) enforces invariants; persistence is
expressed as ports (:class:`TripPlanRepository`) implemented by the
infrastructure layer.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Protocol


@dataclass(frozen=True)
class Preference:
    """A travel preference as an immutable value object."""

    name: str

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("preference name must not be empty")

    def __str__(self) -> str:
        return self.name.strip().lower()


@dataclass(frozen=True)
class Budget:
    """Total budget in CNY; invariant: must be positive."""

    amount: float

    def __post_init__(self) -> None:
        if self.amount <= 0:
            raise ValueError(f"budget must be positive, got {self.amount}")


@dataclass
class HotelOption:
    name: str
    score: float = 0.0
    price: float = 0.0
    reason: str = ""


@dataclass
class TransportOption:
    name: str
    score: float = 0.0
    price: float = 0.0
    reason: str = ""


@dataclass
class TripPlan:
    """Aggregate root: a planned trip and its candidate options.

    Invariants enforced here:
    - days within [1, 30]
    - travelers >= 1
    - a plan must have at least one hotel and one transport option before it
      can be marked ``confirmed``

    Domain events are recorded on the aggregate (``events``) for the
    application layer to publish after persistence succeeds:
    - ``TripPlanCreated`` - on first materialization
    - ``TripPlanOptionsAttached`` - when candidates are attached
    - ``TripPlanConfirmed`` - the finalize transition (``confirm()``)
    """

    city: str
    days: int
    budget: Budget
    travelers: int = 1
    preferences: List[Preference] = field(default_factory=list)
    membership_tier: str = "basic"
    plan_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    created_at_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    status: str = "draft"
    hotel_options: List[HotelOption] = field(default_factory=list)
    transport_options: List[TransportOption] = field(default_factory=list)
    itinerary: List[Dict[str, object]] = field(default_factory=list)
    events: List[Dict[str, str]] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        if not self.city or not self.city.strip():
            raise ValueError("city must not be empty")
        if not 1 <= self.days <= 30:
            raise ValueError(f"days must be within [1, 30], got {self.days}")
        if self.travelers < 1:
            raise ValueError(f"travelers must be >= 1, got {self.travelers}")
        self.preferences = [p if isinstance(p, Preference) else Preference(str(p)) for p in self.preferences]
        # Domain event: TripPlanCreated is recorded exactly once, when the
        # aggregate is first materialized. Rehydrated aggregates come back
        # with their stored event history (non-empty ``events``) and must not
        # emit a second creation event.
        if not self.events:
            self._raise(
                "TripPlanCreated",
                {
                    "plan_id": self.plan_id,
                    "city": self.city,
                    "days": self.days,
                    "travelers": self.travelers,
                    "budget": self.budget.amount,
                    "membership_tier": self.membership_tier,
                },
            )

    def attach_options(
        self,
        hotels: List[HotelOption],
        transports: List[TransportOption],
        itinerary: List[Dict[str, object]],
    ) -> None:
        self.hotel_options = list(hotels)
        self.transport_options = list(transports)
        self.itinerary = list(itinerary)
        self._raise("TripPlanOptionsAttached", {"hotels": len(hotels), "transports": len(transports)})

    def confirm(self) -> None:
        if not self.hotel_options:
            raise ValueError("cannot confirm a plan without hotel options")
        if not self.transport_options:
            raise ValueError("cannot confirm a plan without transport options")
        self.status = "confirmed"
        self._raise("TripPlanConfirmed", {"plan_id": self.plan_id})

    def _raise(self, event: str, payload: Dict[str, object]) -> None:
        self.events.append({"event": event, "at_ms": str(int(time.time() * 1000)), "payload": str(payload)})

    def to_summary(self) -> Dict[str, object]:
        return {
            "plan_id": self.plan_id,
            "city": self.city,
            "days": self.days,
            "budget": self.budget.amount,
            "travelers": self.travelers,
            "membership_tier": self.membership_tier,
            "status": self.status,
            "hotel_count": len(self.hotel_options),
            "transport_count": len(self.transport_options),
            "itinerary_days": len(self.itinerary),
        }


class TripPlanRepository(Protocol):
    """Port: persistence for TripPlan aggregates (CQRS write model)."""

    def save(self, plan: TripPlan) -> None: ...

    def get(self, plan_id: str) -> Optional[TripPlan]: ...

    def list_by_city(self, city: str, limit: int = 10) -> List[TripPlan]: ...
