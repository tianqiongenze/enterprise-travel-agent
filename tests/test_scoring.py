"""Module provides service components and helpers."""

import unittest

from src.travel_agent.recommendation.scoring import hotel_score, tag_multiplier, transport_score


class ScoringTestCase(unittest.TestCase):
    def test_tag_multiplier_applies_weight_product(self) -> None:
        result = tag_multiplier(["family", "kids"], {"family": 1.2, "kids": 1.3})
        self.assertAlmostEqual(result, 1.56)

    def test_hotel_score_rewards_quality_and_budget(self) -> None:
        base = hotel_score(price=800, rating=4.0, tags=["comfort"], budget=1600, weights={"comfort": 1.0})
        boosted = hotel_score(price=800, rating=4.0, tags=["comfort"], budget=1600, weights={"comfort": 1.3})
        self.assertGreater(boosted, base)

    def test_transport_score_penalizes_long_duration(self) -> None:
        fast = transport_score(price=700, duration=2.0, tags=["fast"], budget=1000, weights={"fast": 1.0})
        slow = transport_score(price=700, duration=6.0, tags=["fast"], budget=1000, weights={"fast": 1.0})
        self.assertGreater(fast, slow)


if __name__ == "__main__":
    unittest.main()
