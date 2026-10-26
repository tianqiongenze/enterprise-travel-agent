"""Prometheus metrics (fourth-round R8, plan §四.R8).

Counters/histograms for the runtime API surface — exported at ``/metrics``.
Uses prometheus_client if available; falls back to a tiny in-process
registry writing the same text exposition format (fail-open, never breaks
requests — lesson from the kind staging retest).

Metrics:
- travel_runtime_requests_total{route,code}
- travel_runtime_request_latency_seconds (summary with quantiles)
- travel_runtime_rejects_total{reason}         (token bucket / inflight / circuit)
- travel_cache_l1_hits_total etc.               (from MultiLevelCache)
"""

from __future__ import annotations

import threading
import time
from typing import Dict

try:
    from prometheus_client import (
        CollectorRegistry,
        Counter,
        Histogram,
        generate_latest,
    )

    _HAS_PROM = True
except ImportError:  # pragma: no cover
    _HAS_PROM = False


class _FallbackSeries:
    """Text-format counter/summary good enough for scraping tests."""

    def __init__(self) -> None:
        self.counters: Dict[tuple, float] = {}
        self.observations: Dict[str, list[float]] = {}

    def inc(self, labels: tuple, value: float = 1.0) -> None:
        self.counters[labels] = self.counters.get(labels, 0.0) + value

    def observe(self, name: str, value: float) -> None:
        self.observations.setdefault(name, []).append(value)


class RuntimeMetrics:
    """Facade over prometheus_client (or the fallback)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._started = time.time()
        if _HAS_PROM:
            self._registry = CollectorRegistry()
            self.requests = Counter(
                "travel_runtime_requests_total",
                "HTTP requests handled",
                ["route", "code"],
                registry=self._registry,
            )
            self.latency = Histogram(
                "travel_runtime_request_latency_seconds",
                "Request latency",
                ["route"],
                registry=self._registry,
            )
            self.rejects = Counter(
                "travel_runtime_rejects_total",
                "Requests rejected by guard",
                ["reason"],
                registry=self._registry,
            )
        else:
            self._fallback = _FallbackSeries()
            self.requests = _FallbackCounter(self._fallback, "travel_runtime_requests_total")
            self.latency = _FallbackHistogram(self._fallback, "travel_runtime_request_latency_seconds")
            self.rejects = _FallbackCounter(self._fallback, "travel_runtime_rejects_total")

    def observe_request(self, route: str, code: int, seconds: float) -> None:
        self.requests.labels(route=route, code=str(code)).inc()
        self.latency.labels(route=route).observe(seconds)

    def observe_reject(self, reason: str) -> None:
        self.rejects.labels(reason=reason).inc()

    def render(self, extra: str = "") -> bytes:
        if _HAS_PROM:
            body = generate_latest(self._registry)
        else:
            lines = []
            for (metric, labels), value in sorted(self._fallback.counters.items()):
                label_str = "".join(f'{k}="{v}",' for k, v in labels)
                lines.append(f"{metric}{{{label_str.rstrip(',')}}} {value}")
            for name, values in self._fallback.observations.items():
                if values:
                    vs = sorted(values)
                    n = len(vs)
                    lines.append(f"{name}_count {n}")
                    lines.append(f"{name}_sum {sum(vs):.6f}")
                    lines.append(f'{name}{{quantile="0.5"}} {vs[n // 2]:.6f}')
                    lines.append(f'{name}{{quantile="0.95"}} {vs[min(n - 1, int(n * 0.95))]:.6f}')
                    lines.append(f'{name}{{quantile="0.99"}} {vs[min(n - 1, int(n * 0.99))]:.6f}')
            lines.append(f"travel_runtime_uptime_seconds {time.time() - self._started:.1f}")
            body = ("\n".join(lines) + "\n").encode()
        return body + (extra or "").encode()


class _FallbackCounter:
    def __init__(self, series: _FallbackSeries, name: str) -> None:
        self._series = series
        self._name = name

    def labels(self, **labels):  # noqa: D102
        outer = self

        class _Child:
            def inc(self, value: float = 1.0) -> None:
                outer._series.inc((outer._name, tuple(sorted(labels.items()))), value)

        return _Child()


class _FallbackHistogram:
    def __init__(self, series: _FallbackSeries, name: str) -> None:
        self._series = series
        self._name = name

    def labels(self, **labels):  # noqa: D102
        outer = self

        class _Child:
            def observe(self, value: float) -> None:
                outer._series.observe(f'{outer._name}{{route="{labels.get("route", "")}"}}', value)

        return _Child()


runtime_metrics = RuntimeMetrics()
