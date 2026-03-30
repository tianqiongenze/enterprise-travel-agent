"""Module provides service components and helpers."""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class TravelRequest:
    city: str
    days: int
    budget: float
    travelers: int = 1
    preferences: List[str] = field(default_factory=list)
    membership_tier: str = "basic"


@dataclass
class RecommendationItem:
    id: str
    name: str
    score: float
    price: float
    tags: List[str]
    reason: str


@dataclass
class TravelRecommendation:
    hotel_options: List[RecommendationItem]
    transport_options: List[RecommendationItem]
    itinerary: List[Dict[str, str]]
    engagement_recommendations: List[Dict[str, str]] = field(default_factory=list)
