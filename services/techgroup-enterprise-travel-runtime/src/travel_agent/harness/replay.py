"""Module provides service components and helpers."""

import copy
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List

from ..models import TravelRequest


@dataclass
class HarnessRecord:
    request: Dict[str, Any]
    engine_name: str
    engine_metadata: Dict[str, str]
    a2a_logs: List[Dict[str, Any]] = field(default_factory=list)
    mcp_logs: List[Dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


class OrchestrationHarness:
    def __init__(self, max_records: int = 50) -> None:
        self.max_records = max(1, max_records)
        self.records: List[HarnessRecord] = []

    def capture(
        self,
        request: TravelRequest,
        engine_name: str,
        engine_metadata: Dict[str, str],
        a2a_logs: List[Dict[str, Any]],
        mcp_logs: List[Dict[str, Any]],
    ) -> None:
        record = HarnessRecord(
            request={
                "city": request.city,
                "days": request.days,
                "budget": request.budget,
                "travelers": request.travelers,
                "preferences": list(request.preferences),
            },
            engine_name=engine_name,
            engine_metadata=dict(engine_metadata),
            a2a_logs=copy.deepcopy(a2a_logs),
            mcp_logs=copy.deepcopy(mcp_logs[-10:]),
        )
        self.records.append(record)
        if len(self.records) > self.max_records:
            self.records = self.records[-self.max_records :]

    def replay_last(self, orchestrator: Any) -> Dict[str, object]:
        if not self.records:
            return {"ok": False, "reason": "no-harness-record"}

        payload = self.records[-1].request
        replay_request = TravelRequest(
            city=str(payload.get("city", "")),
            days=int(payload.get("days", 1)),
            budget=float(payload.get("budget", 0.0)),
            travelers=int(payload.get("travelers", 1)),
            preferences=[str(item) for item in payload.get("preferences", [])],
        )
        result = orchestrator.recommend(replay_request)
        return {
            "ok": True,
            "engine": getattr(orchestrator.engine, "name", "unknown"),
            "hotel_count": len(result.hotel_options),
            "transport_count": len(result.transport_options),
            "engagement_count": len(result.engagement_recommendations),
        }

