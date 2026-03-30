"""Module provides service components and helpers."""

from typing import Dict, List


def tag_multiplier(tags: List[str], weights: Dict[str, float]) -> float:
    score = 1.0
    for tag in tags:
        score *= weights.get(tag, 1.0)
    return score


def hotel_score(price: float, rating: float, tags: List[str], budget: float, weights: Dict[str, float]) -> float:
    price_factor = min(1.4, budget / max(price, 1.0))
    quality_factor = rating / 5.0
    return (price_factor * 0.45 + quality_factor * 0.55) * tag_multiplier(tags, weights)


def transport_score(price: float, duration: float, tags: List[str], budget: float, weights: Dict[str, float]) -> float:
    price_factor = min(1.5, budget / max(price, 1.0))
    speed_factor = 1.0 / max(duration, 0.5)
    return (price_factor * 0.55 + speed_factor * 0.45) * tag_multiplier(tags, weights)
