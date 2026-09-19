"""Module provides service components and helpers."""

import hashlib
import importlib
import json
import os
import sys
import threading
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any, Optional, cast

grpc = importlib.import_module("grpc")
requests = importlib.import_module("requests")


def _load_grpc_stubs() -> tuple[ModuleType, ModuleType]:
    try:
        pb2 = importlib.import_module("..grpc.generated.v1.ranker_pb2", package=__package__)
        pb2_grpc = importlib.import_module("..grpc.generated.v1.ranker_pb2_grpc", package=__package__)
        return pb2, pb2_grpc
    except ModuleNotFoundError:
        # grpc_tools emits flat imports (e.g. `import ranker_pb2`) in *_pb2_grpc.py.
        # Add generated stub folder to sys.path so package import works reliably.
        generated_dir = Path(__file__).resolve().parents[1] / "grpc" / "generated" / "v1"
        generated_path = str(generated_dir)
        if generated_path not in sys.path:
            sys.path.insert(0, generated_path)
        pb2 = importlib.import_module("ranker_pb2")
        pb2_grpc = importlib.import_module("ranker_pb2_grpc")
        return pb2, pb2_grpc


ranker_pb2, ranker_pb2_grpc = _load_grpc_stubs()


class GoRankerClient:
    def __init__(self) -> None:
        self.backend: str = os.getenv("TRAVEL_RANKER_BACKEND", "python").strip().lower()
        self.base_url: str = os.getenv("TRAVEL_GO_RANKER_URL", "http://localhost:8090").rstrip("/")
        self.grpc_target: str = os.getenv("TRAVEL_GO_RANKER_GRPC_TARGET", "localhost:9090").strip()
        self.transport: str = os.getenv("TRAVEL_GO_RANKER_TRANSPORT", "auto").strip().lower()
        self.grpc_fallback_http: bool = os.getenv("TRAVEL_GO_RANKER_GRPC_FALLBACK_HTTP", "true").strip().lower() in {"1", "true", "yes"}
        self.timeout: float = float(os.getenv("TRAVEL_GO_RANKER_TIMEOUT", "0.4"))
        self.canary_percent: int = int(os.getenv("TRAVEL_RANKER_CANARY_PERCENT", "0"))
        self.shadow: bool = os.getenv("TRAVEL_GO_RANKER_SHADOW", "false").strip().lower() in {"1", "true", "yes"}
        self.diff_threshold: float = float(os.getenv("TRAVEL_GO_RANKER_DIFF_THRESHOLD", "0.08"))
        self.metrics_path: str = os.getenv("TRAVEL_RANKER_METRICS_PATH", "stress/ranker_transport_metrics.prom")
        self.metrics_flush_interval_sec: float = float(os.getenv("TRAVEL_RANKER_METRICS_FLUSH_INTERVAL_SEC", "5"))
        self._last_metrics_flush_at: float = 0.0
        self._metrics_lock = threading.Lock()
        self._grpc_channel = None
        self._grpc_stub = None
        self._metrics: dict[str, float] = {
            "travel_ranker_grpc_attempt_total": 0.0,
            "travel_ranker_grpc_success_total": 0.0,
            "travel_ranker_grpc_error_total": 0.0,
            "travel_ranker_http_attempt_total": 0.0,
            "travel_ranker_http_success_total": 0.0,
            "travel_ranker_http_error_total": 0.0,
            "travel_ranker_fallback_http_total": 0.0,
            "travel_ranker_shadow_diff_total": 0.0,
        }

    def score_hotel(self, price: float, rating: float, tags: list[str], budget: float, weights: dict[str, float]) -> float | None:
        payload = {
            "price": price,
            "rating": rating,
            "duration": 0.0,
            "tags": tags,
            "budget": budget,
            "weights": weights,
        }
        return self._score("hotel", payload)

    def score_transport(self, price: float, duration: float, tags: list[str], budget: float, weights: dict[str, float]) -> float | None:
        payload = {
            "price": price,
            "rating": 0.0,
            "duration": duration,
            "tags": tags,
            "budget": budget,
            "weights": weights,
        }
        return self._score("transport", payload)

    def shadow_compare(self, score_type: str, payload: Mapping[str, Any], python_score: float) -> None:
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

    def _score(self, score_type: str, payload: Mapping[str, Any]) -> float | None:
        if self.backend == "python":
            return None
        if self.backend == "canary" and not self._should_use_go(score_type, payload):
            return None
        if self.backend not in {"go", "canary"}:
            return None
        return self._score_raw(score_type, payload)

    def score_batch(self, score_type: str, payloads: Sequence[Mapping[str, Any]]) -> list[float | None] | None:
        if not payloads:
            return []
        if self.backend == "python":
            return None
        if self.backend == "canary":
            go_enabled = [self._should_use_go(score_type, payload) for payload in payloads]
            if not any(go_enabled):
                return None
            go_payloads = [dict(payload) for payload, enabled in zip(payloads, go_enabled) if enabled]
            go_scores = self._request_batch_http(score_type, go_payloads)
            if go_scores is None:
                return None
            merged: list[float | None] = []
            cursor = 0
            for enabled in go_enabled:
                if enabled:
                    merged.append(go_scores[cursor] if cursor < len(go_scores) else None)
                    cursor += 1
                else:
                    merged.append(None)
            return merged
        if self.backend != "go":
            return None
        return self._request_batch_http(score_type, [dict(payload) for payload in payloads])

    def score_hotel_batch(self, payloads: Sequence[Mapping[str, Any]]) -> list[float | None] | None:
        return self.score_batch("hotel", payloads)

    def score_transport_batch(self, payloads: Sequence[Mapping[str, Any]]) -> list[float | None] | None:
        return self.score_batch("transport", payloads)

    def _should_use_go(self, score_type: str, payload: Mapping[str, Any]) -> bool:
        percent = max(0, min(100, self.canary_percent))
        if percent == 0:
            return False
        if percent == 100:
            return True
        raw = score_type + ":" + json.dumps(payload, ensure_ascii=False, sort_keys=True)
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        bucket = int(digest[:8], 16) % 100
        return bucket < percent

    def _score_raw(self, score_type: str, payload: Mapping[str, Any]) -> float | None:
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

    def _request_score_grpc(self, score_type: str, payload: Mapping[str, Any]) -> float | None:
        self._metrics["travel_ranker_grpc_attempt_total"] += 1.0
        price = self._as_float(payload.get("price", 0.0))
        rating = self._as_float(payload.get("rating", 0.0))
        duration = self._as_float(payload.get("duration", 0.0))
        tags = self._as_string_list(payload.get("tags", []))
        budget = self._as_float(payload.get("budget", 0.0))
        weights = self._as_float_map(payload.get("weights", {}))
        request = cast(Any, ranker_pb2).ScoreRequest(
            price=price,
            rating=rating,
            duration=duration,
            tags=tags,
            budget=budget,
            weights=weights,
        )
        try:
            stub = self._ensure_grpc_stub()
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
            self._grpc_channel = None
            self._grpc_stub = None
            self._metrics["travel_ranker_grpc_error_total"] += 1.0
            self._flush_metrics()
            return None

    def _request_score_http(self, score_type: str, payload: Mapping[str, Any]) -> float | None:
        self._metrics["travel_ranker_http_attempt_total"] += 1.0
        try:
            response = requests.post(
                f"{self.base_url}/v1/score/{score_type}",
                json=dict(payload),
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

    def _request_batch_http(self, score_type: str, payloads: Sequence[Mapping[str, Any]]) -> list[float | None] | None:
        self._metrics["travel_ranker_http_attempt_total"] += float(len(payloads))
        try:
            serialized_payloads = [dict(payload) for payload in payloads]
            response = requests.post(
                f"{self.base_url}/v1/score/{score_type}/batch",
                json={"items": serialized_payloads},
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            raw_scores = data.get("scores", [])
            if not isinstance(raw_scores, list):
                self._metrics["travel_ranker_http_error_total"] += float(len(payloads))
                self._flush_metrics()
                return None
            normalized: list[float | None] = []
            success = 0.0
            for score in raw_scores:
                try:
                    parsed = float(score)
                    if parsed > 0.0:
                        success += 1.0
                        normalized.append(parsed)
                    else:
                        normalized.append(None)
                except (TypeError, ValueError):
                    normalized.append(None)
            self._metrics["travel_ranker_http_success_total"] += success
            error_count = max(0.0, float(len(payloads)) - success)
            self._metrics["travel_ranker_http_error_total"] += error_count
            self._flush_metrics()
            return normalized
        except (requests.RequestException, ValueError, TypeError):
            self._metrics["travel_ranker_http_error_total"] += float(len(payloads))
            self._flush_metrics()
            return None

    def _flush_metrics(self) -> None:
        now = time.time()
        if now - self._last_metrics_flush_at < self.metrics_flush_interval_sec:
            return
        with self._metrics_lock:
            now = time.time()
            if now - self._last_metrics_flush_at < self.metrics_flush_interval_sec:
                return
            self._last_metrics_flush_at = now
            metrics_snapshot = dict(self._metrics)
        metrics_file = Path(self.metrics_path)
        metrics_file.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            f"{name} {value}"
            for name, value in sorted(metrics_snapshot.items())
        ]
        lines.append(f"travel_ranker_metrics_timestamp {time.time()}")
        metrics_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _ensure_grpc_stub(self) -> Any:
        if self._grpc_stub is not None:
            return self._grpc_stub
        channel = grpc.insecure_channel(self.grpc_target)
        self._grpc_channel = channel
        self._grpc_stub = ranker_pb2_grpc.RankerServiceStub(channel)
        return self._grpc_stub

    def _as_float(self, value: object, fallback: float = 0.0) -> float:
        if isinstance(value, bool):
            return float(value)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return fallback
        return fallback

    def _as_string_list(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value]

    def _as_float_map(self, value: object) -> dict[str, float]:
        if not isinstance(value, dict):
            return {}
        normalized: dict[str, float] = {}
        for key, item in value.items():
            normalized[str(key)] = self._as_float(item)
        return normalized

