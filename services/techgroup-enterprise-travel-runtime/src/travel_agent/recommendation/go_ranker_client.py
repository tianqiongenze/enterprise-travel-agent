"""Module provides service components and helpers."""

import os
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import grpc
import requests

try:
    from ..grpc.generated.v1 import ranker_pb2
    from ..grpc.generated.v1 import ranker_pb2_grpc
except ModuleNotFoundError:
    # grpc_tools emits flat imports (e.g. `import ranker_pb2`) in *_pb2_grpc.py.
    # Add generated stub folder to sys.path so package import works reliably.
    generated_dir = Path(__file__).resolve().parents[1] / "grpc" / "generated" / "v1"
    generated_path = str(generated_dir)
    if generated_path not in sys.path:
        sys.path.insert(0, generated_path)
    import ranker_pb2  # type: ignore
    import ranker_pb2_grpc  # type: ignore


class GoRankerClient:
    def __init__(self) -> None:
        self.backend = os.getenv("TRAVEL_RANKER_BACKEND", "python").strip().lower()
        self.base_url = os.getenv("TRAVEL_GO_RANKER_URL", "http://localhost:8090").rstrip("/")
        self.grpc_target = os.getenv("TRAVEL_GO_RANKER_GRPC_TARGET", "localhost:9090").strip()
        self.transport = os.getenv("TRAVEL_GO_RANKER_TRANSPORT", "auto").strip().lower()
        self.grpc_fallback_http = os.getenv("TRAVEL_GO_RANKER_GRPC_FALLBACK_HTTP", "true").strip().lower() in {"1", "true", "yes"}
        self.timeout = float(os.getenv("TRAVEL_GO_RANKER_TIMEOUT", "0.4"))
        self.canary_percent = int(os.getenv("TRAVEL_RANKER_CANARY_PERCENT", "0"))
        self.shadow = os.getenv("TRAVEL_GO_RANKER_SHADOW", "false").strip().lower() in {"1", "true", "yes"}
        self.diff_threshold = float(os.getenv("TRAVEL_GO_RANKER_DIFF_THRESHOLD", "0.08"))
        self.metrics_path = os.getenv("TRAVEL_RANKER_METRICS_PATH", "stress/ranker_transport_metrics.prom")
        self._metrics: Dict[str, float] = {
            "travel_ranker_grpc_attempt_total": 0.0,
            "travel_ranker_grpc_success_total": 0.0,
            "travel_ranker_grpc_error_total": 0.0,
            "travel_ranker_http_attempt_total": 0.0,
            "travel_ranker_http_success_total": 0.0,
            "travel_ranker_http_error_total": 0.0,
            "travel_ranker_fallback_http_total": 0.0,
            "travel_ranker_shadow_diff_total": 0.0,
        }

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
            self._metrics["travel_ranker_shadow_diff_total"] += 1.0
            self._flush_metrics()
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
        transport = self.transport if self.transport in {"auto", "grpc", "http"} else "auto"
        if transport in {"grpc", "auto"}:
            grpc_score = self._request_score_grpc(score_type, payload)
            if grpc_score is not None:
                return grpc_score
            self._metrics["travel_ranker_fallback_http_total"] += 1.0
            if transport == "grpc" and not self.grpc_fallback_http:
                self._flush_metrics()
                return None
        return self._request_score_http(score_type, payload)

    def _request_score_grpc(self, score_type: str, payload: Dict[str, object]) -> Optional[float]:
        self._metrics["travel_ranker_grpc_attempt_total"] += 1.0
        price = self._as_float(payload.get("price", 0.0))
        rating = self._as_float(payload.get("rating", 0.0))
        duration = self._as_float(payload.get("duration", 0.0))
        tags = self._as_string_list(payload.get("tags", []))
        budget = self._as_float(payload.get("budget", 0.0))
        weights = self._as_float_map(payload.get("weights", {}))
        request = ranker_pb2.ScoreRequest(  # type: ignore[attr-defined]
            price=price,
            rating=rating,
            duration=duration,
            tags=tags,
            budget=budget,
            weights=weights,
        )
        try:
            with grpc.insecure_channel(self.grpc_target) as channel:
                stub = ranker_pb2_grpc.RankerServiceStub(channel)
                if score_type == "hotel":
                    response = stub.ScoreHotel(request, timeout=self.timeout)
                else:
                    response = stub.ScoreTransport(request, timeout=self.timeout)
                score = float(response.score)
                if score > 0.0:
                    self._metrics["travel_ranker_grpc_success_total"] += 1.0
                self._flush_metrics()
                return score if score > 0.0 else None
        except (grpc.RpcError, ValueError, TypeError):
            self._metrics["travel_ranker_grpc_error_total"] += 1.0
            self._flush_metrics()
            return None

    def _request_score_http(self, score_type: str, payload: Dict[str, object]) -> Optional[float]:
        self._metrics["travel_ranker_http_attempt_total"] += 1.0
        try:
            response = requests.post(
                f"{self.base_url}/v1/score/{score_type}",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            score = float(data.get("score", 0.0))
            if score > 0.0:
                self._metrics["travel_ranker_http_success_total"] += 1.0
            self._flush_metrics()
            return score if score > 0.0 else None
        except (requests.RequestException, ValueError, TypeError):
            self._metrics["travel_ranker_http_error_total"] += 1.0
            self._flush_metrics()
            return None

    def _flush_metrics(self) -> None:
        metrics_file = Path(self.metrics_path)
        metrics_file.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            f"{name} {value}"
            for name, value in sorted(self._metrics.items())
        ]
        lines.append(f"travel_ranker_metrics_timestamp {time.time()}")
        metrics_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _as_float(self, value: object, fallback: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return fallback

    def _as_string_list(self, value: object) -> List[str]:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value]

    def _as_float_map(self, value: object) -> Dict[str, float]:
        if not isinstance(value, dict):
            return {}
        normalized: Dict[str, float] = {}
        for key, item in value.items():
            normalized[str(key)] = self._as_float(item)
        return normalized

