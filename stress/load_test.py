"""Module provides service components and helpers."""

import argparse
import json
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from statistics import mean

import requests


def _single_call(base_url: str, timeout_sec: int) -> dict:
    payload = {
        "city": random.choice(["北京", "上海", "成都"]),
        "days": random.choice([2, 3, 4]),
        "budget": random.choice([2600, 3000, 3600, 4200]),
        "travelers": random.choice([1, 2, 3]),
        "preferences": random.choice([["family"], ["budget"], ["comfort"], ["family", "budget"]]),
    }
    start = time.perf_counter()
    try:
        response = requests.post(base_url.rstrip("/") + "/recommend", json=payload, timeout=timeout_sec)
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
    parser = argparse.ArgumentParser(description="Load test for enterprise travel API")
    parser.add_argument("--base-url", default="http://localhost:8000", help="API base url")
    parser.add_argument("--requests", type=int, default=1000, help="Total request count")
    parser.add_argument("--concurrency", type=int, default=100, help="Concurrent workers")
    parser.add_argument("--timeout", type=int, default=8, help="Request timeout in seconds")
    parser.add_argument("--out", default="stress/report.json", help="Output report path")
    args = parser.parse_args()

    report = run(args.base_url, args.requests, args.concurrency, args.timeout)
    with open(args.out, "w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
