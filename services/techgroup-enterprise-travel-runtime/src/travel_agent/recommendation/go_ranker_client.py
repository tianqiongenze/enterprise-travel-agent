"""Module provides service components and helpers."""

import os
import hashlib
import json
from typing import Dict, List, Optional

import requests


class GoRankerClient:
    def __init__(self) -> None:
        self.backend = os.getenv("TRAVEL_RANKER_BACKEND", "python").strip().lower()
        self.base_url = os.getenv("TRAVEL_GO_RANKER_URL", "http://localhost:8090").rstrip("/")
        self.timeout = float(os.getenv("TRAVEL_GO_RANKER_TIMEOUT", "0.4"))
        self.canary_percent = int(os.getenv("TRAVEL_RANKER_CANARY_PERCENT", "0"))
        self.shadow = os.getenv("TRAVEL_GO_RANKER_SHADOW", "false").strip().lower() in {"1", "true", "yes"}
        self.diff_threshold = float(os.getenv("TRAVEL_GO_RANKER_DIFF_THRESHOLD", "0.08"))

    def score_hotel(self, price: float, rating: float, tags: List[str], budget: float, weights: Dict[str, float]) -> Optional[float]:
        payload = {
            "price": price,
            "rating": rating,
            "duration": 0.0,
            "tags": tags,
            "budget": budget,
            "weights": weights,
        }
        return self._score("hotel", payload)

    def score_transport(self, price: float, duration: float, tags: List[str], budget: float, weights: Dict[str, float]) -> Optional[float]:
        payload = {
            "price": price,
            "rating": 0.0,
            "duration": duration,
            "tags": tags,
            "budget": budget,
            "weights": weights,
        }
        return self._score("transport", payload)

    def shadow_compare(self, score_type: str, payload: Dict[str, object], python_score: float) -> None:
        if not self.shadow:
            return
        go_score = self._score_raw(score_type, payload)
        if go_score is None:
            return
        diff = abs(go_score - python_score)
        if diff >= self.diff_threshold:
            print(
                "go_ranker_shadow_diff score_type=%s python=%.6f go=%.6f diff=%.6f threshold=%.6f"
                % (score_type, python_score, go_score, diff, self.diff_threshold)
            )

    def _score(self, score_type: str, payload: Dict[str, object]) -> Optional[float]:
        if self.backend == "python":
            return None
        if self.backend == "canary" and not self._should_use_go(score_type, payload):
            return None
        if self.backend not in {"go", "canary"}:
            return None
        return self._score_raw(score_type, payload)

    def _should_use_go(self, score_type: str, payload: Dict[str, object]) -> bool:
        percent = max(0, min(100, self.canary_percent))
        if percent == 0:
            return False
        if percent == 100:
            return True
        raw = score_type + ":" + json.dumps(payload, ensure_ascii=False, sort_keys=True)
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        bucket = int(digest[:8], 16) % 100
        return bucket < percent

    def _score_raw(self, score_type: str, payload: Dict[str, object]) -> Optional[float]:
        return self._request_score(score_type, payload)

    def _request_score(self, score_type: str, payload: Dict[str, object]) -> Optional[float]:
        try:
            response = requests.post(
                f"{self.base_url}/v1/score/{score_type}",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            score = float(data.get("score", 0.0))
            return score if score > 0.0 else None
        except (requests.RequestException, ValueError, TypeError):
            return None
