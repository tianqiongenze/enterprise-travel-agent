"""Shared schema adapters for external load-test JSON exports."""

from __future__ import annotations

from typing import Dict, Tuple


def to_percent(value: float) -> float:
    """Normalize ratio-like values (0-1) and percent-like values (0-100)."""
    return value * 100.0 if value <= 1.0 else value


def detect_benchmark_schema(source: Dict[str, object]) -> str:
    if isinstance(source.get("metrics"), dict) and isinstance(source.get("root_group"), dict):
        return "k6"
    if "Total" in source and isinstance(source.get("Total"), dict):
        return "jmeter"
    if "stats_total" in source and isinstance(source.get("stats_total"), dict):
        return "locust"
    if "user_count" in source or "fail_ratio" in source:
        return "locust"
    return "native"


def parse_native(source: Dict[str, object]) -> Tuple[int, float, float, float]:
    achieved = int(source.get("achievedConcurrency", source.get("concurrency", 0)) or 0)
    p95 = float(source.get("p95Ms", source.get("p95_latency_ms", source.get("p95_ms", source.get("p95", 0.0)))) or 0.0)
    p99 = float(source.get("p99Ms", source.get("p99_latency_ms", source.get("p99_ms", source.get("p99", 0.0)))) or 0.0)
    success_rate = to_percent(float(source.get("successRatePercent", source.get("success_rate", 0.0)) or 0.0))
    error_rate = max(0.0, 100.0 - success_rate)
    return achieved, p95, p99, error_rate


def parse_k6(source: Dict[str, object]) -> Tuple[int, float, float, float]:
    metrics = source.get("metrics", {}) if isinstance(source.get("metrics"), dict) else {}
    vus = metrics.get("vus_max", {}) if isinstance(metrics.get("vus_max"), dict) else {}
    http_reqs = metrics.get("http_reqs", {}) if isinstance(metrics.get("http_reqs"), dict) else {}
    req_values = http_reqs.get("values", {}) if isinstance(http_reqs.get("values"), dict) else {}

    # Some k6 runs only expose request counts and not vus_max; use count as fallback signal.
    achieved = int(vus.get("value", req_values.get("count", 0)) or 0)

    duration = metrics.get("http_req_duration", {}) if isinstance(metrics.get("http_req_duration"), dict) else {}
    duration_values = duration.get("values", {}) if isinstance(duration.get("values"), dict) else {}
    p95 = float(duration_values.get("p(95)", duration_values.get("p95", 0.0)) or 0.0)
    p99 = float(duration_values.get("p(99)", duration_values.get("p99", 0.0)) or 0.0)

    checks = metrics.get("checks", {}) if isinstance(metrics.get("checks"), dict) else {}
    check_values = checks.get("values", {}) if isinstance(checks.get("values"), dict) else {}
    passes = float(check_values.get("passes", 0.0) or 0.0)
    fails = float(check_values.get("fails", 0.0) or 0.0)
    total = passes + fails
    error_rate = (fails / total * 100.0) if total > 0 else 100.0
    return achieved, p95, p99, error_rate


def parse_jmeter(source: Dict[str, object]) -> Tuple[int, float, float, float]:
    # Dashboard statistics.json usually stores aggregated metrics under "Total".
    total = source.get("Total", {}) if isinstance(source.get("Total"), dict) else source
    achieved = int(total.get("concurrency", total.get("threads", total.get("sampleCount", 0))) or 0)

    p95 = float(
        total.get(
            "pct95",
            total.get(
                "p95",
                total.get("pct2ResTime", 0.0),
            ),
        )
        or 0.0
    )
    p99 = float(total.get("pct99", total.get("p99", total.get("pct3ResTime", 0.0))) or 0.0)
    # JMeter dashboard "errorPct" is already a percentage (0.5 means 0.5%);
    # only the legacy "errorRate" field is a 0-1 ratio that needs normalization.
    if "errorPct" in total:
        error_rate = min(100.0, max(0.0, float(total.get("errorPct") or 0.0)))
    else:
        error_rate = to_percent(float(total.get("errorRate", 0.0) or 0.0))
    return achieved, p95, p99, error_rate


def parse_locust(source: Dict[str, object]) -> Tuple[int, float, float, float]:
    if "stats_total" in source and isinstance(source.get("stats_total"), dict):
        stats_total = source.get("stats_total", {})
        achieved = int(source.get("user_count", source.get("user_count_max", 0)) or 0)
        p95 = float(stats_total.get("response_time_percentile_0.95", stats_total.get("p95", 0.0)) or 0.0)
        p99 = float(stats_total.get("response_time_percentile_0.99", stats_total.get("p99", 0.0)) or 0.0)
        num_failures = float(stats_total.get("num_failures", 0.0) or 0.0)
        num_requests = float(stats_total.get("num_requests", 0.0) or 0.0)
        total = num_failures + num_requests
        error_rate = (num_failures / total * 100.0) if total > 0 else to_percent(float(source.get("fail_ratio", 1.0) or 1.0))
        return achieved, p95, p99, error_rate

    achieved = int(source.get("user_count", source.get("concurrency", 0)) or 0)
    p95 = float(source.get("response_time_percentile_0.95", source.get("p95", 0.0)) or 0.0)
    p99 = float(source.get("response_time_percentile_0.99", source.get("p99", 0.0)) or 0.0)
    fail_ratio = float(source.get("fail_ratio", source.get("error_rate", 1.0)) or 0.0)
    error_rate = to_percent(fail_ratio)
    return achieved, p95, p99, error_rate


def parse_benchmark(source: Dict[str, object], schema: str) -> Tuple[int, float, float, float, str]:
    final_schema = detect_benchmark_schema(source) if schema == "auto" else schema
    if final_schema == "k6":
        achieved, p95, p99, error_rate = parse_k6(source)
    elif final_schema == "jmeter":
        achieved, p95, p99, error_rate = parse_jmeter(source)
    elif final_schema == "locust":
        achieved, p95, p99, error_rate = parse_locust(source)
    else:
        achieved, p95, p99, error_rate = parse_native(source)
    return achieved, p95, p99, error_rate, final_schema

