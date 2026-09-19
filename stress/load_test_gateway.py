"""Load test for the gateway full path (Gateway -> Policy -> Runtime -> Ranker).

Mirrors stress/load_test.py's report schema so evidence ingest can consume it
(native schema), but targets the gateway's public API and sends a complete
gateway request payload (tenant/user/conversation/idempotency/policy fields).
Uses per-thread pooled sessions - see load_test.py for rationale.
"""

from __future__ import annotations

import argparse
import json
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from statistics import mean

import requests
from requests.adapters import HTTPAdapter

_local = threading.local()


def _session() -> requests.Session:
    session = getattr(_local, "session", None)
    if session is None:
        session = requests.Session()
        adapter = HTTPAdapter(pool_connections=64, pool_maxsize=64, max_retries=0)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        _local.session = session
    return session


def _worker_id() -> int:
    worker = getattr(_local, "worker_id", None)
    if worker is None:
        worker = threading.get_ident() % 100000
        _local.worker_id = worker
    return int(worker)


def _single_call(base_url: str, timeout_sec: int) -> dict:
    worker = _worker_id()
    seq = getattr(_local, "seq", 0) + 1
    _local.seq = seq
    payload = {
        "tenantId": "tenant-loadtest",
        "userId": f"user-{worker}",
        "policyId": "policy-default",
        "conversationId": f"conv-{worker}-{seq}",
        "idempotencyKey": f"idem-{worker}-{seq}-{int(time.time() * 1000)}",
        "city": random.choice(["北京", "上海", "成都"]),
        "days": random.choice([2, 3, 4]),
        "budget": random.choice([2600, 3000, 3600, 4200]),
        "travelers": random.choice([1, 2, 3]),
        "membershipTier": "gold",
        "preferences": random.choice([["family"], ["budget"], ["comfort"], ["family", "budget"]]),
        "maxAgentSteps": 10,
        "maxToolCalls": 10,
        "allowedTools": ["search_hotels", "search_transports", "search_attractions"],
    }
    start = time.perf_counter()
    try:
        response = _session().post(
            base_url.rstrip("/") + "/api/v1/travel/recommend", json=payload, timeout=timeout_sec
        )
        elapsed = (time.perf_counter() - start) * 1000
        return {"ok": response.status_code == 200, "latency_ms": elapsed, "status": response.status_code}
    except Exception:
        elapsed = (time.perf_counter() - start) * 1000
        return {"ok": False, "latency_ms": elapsed, "status": 0}


def run(base_url: str, total_requests: int, concurrency: int, timeout_sec: int) -> dict:
    latencies = []
    ok_count = 0
    status_hist = {}
    lock = threading.Lock()

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(_single_call, base_url, timeout_sec) for _ in range(total_requests)]
        for future in as_completed(futures):
            result = future.result()
            with lock:
                latencies.append(result["latency_ms"])
                if result["ok"]:
                    ok_count += 1
                key = str(result["status"])
                status_hist[key] = status_hist.get(key, 0) + 1

    latencies_sorted = sorted(latencies)
    p95 = latencies_sorted[int(len(latencies_sorted) * 0.95) - 1] if latencies_sorted else 0.0
    p99 = latencies_sorted[int(len(latencies_sorted) * 0.99) - 1] if latencies_sorted else 0.0
    return {
        "target": "gateway-full-path",
        "total_requests": total_requests,
        "concurrency": concurrency,
        "success": ok_count,
        "error": total_requests - ok_count,
        "success_rate": round(ok_count / max(1, total_requests), 4),
        "avg_latency_ms": round(mean(latencies_sorted), 2) if latencies_sorted else 0.0,
        "p95_latency_ms": round(p95, 2),
        "p99_latency_ms": round(p99, 2),
        "status_histogram": status_hist,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Gateway full-path load test")
    parser.add_argument("--base-url", default="http://localhost:8080", help="Gateway base url")
    parser.add_argument("--requests", type=int, default=1000, help="Total request count")
    parser.add_argument("--concurrency", type=int, default=20, help="Concurrent workers")
    parser.add_argument("--timeout", type=int, default=15, help="Request timeout in seconds")
    parser.add_argument("--out", default="stress/report_gateway.json", help="Output report path")
    args = parser.parse_args()

    report = run(args.base_url, args.requests, args.concurrency, args.timeout)
    with open(args.out, "w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
