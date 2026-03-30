"""Module provides service components and helpers."""

import json
import os

from .models import TravelRequest
from .orchestrator import build_orchestrator


def main() -> None:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    orchestrator = build_orchestrator(project_root)
    request = TravelRequest(city="北京", days=3, budget=3000, travelers=2, preferences=["family", "budget"])
    recommendation = orchestrator.recommend(request)
    output = {
        "hotel_options": [item.__dict__ for item in recommendation.hotel_options],
        "transport_options": [item.__dict__ for item in recommendation.transport_options],
        "itinerary": recommendation.itinerary,
        "audit_logs": orchestrator.registry.audit_logs,
        "a2a_logs": orchestrator.a2a_logs,
        "registered_agents": orchestrator.registry_center.list_services(),
        "registered_tools": orchestrator.registry_center.list_tools(),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
