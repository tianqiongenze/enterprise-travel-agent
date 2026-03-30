"""Module provides service components and helpers."""

import argparse
import hashlib
import json
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from statistics import mean
from typing import Any, Dict, List, Tuple

import requests


def _make_signature(idempotency_key: str, shared_secret: str) -> str:
    raw = idempotency_key + "." + shared_secret
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _single_call(
    base_url: str,
    endpoint: str,
    timeout_sec: int,
    request_id: int,
    shared_secret: str,
    internal_client_id: str,
) -> Dict[str, Any]:
    city = random.choice(["北京", "上海", "成都"])
    idem = "idem-%s-%s" % (int(time.time() * 1000), request_id)
    payload = {
        "tenantId": "tenant-canary",
        "userId": "user-canary",
        "policyId": "policy-default",
        "conversationId": "conv-%s" % request_id,
        "idempotencyKey": idem,
        "city": city,
        "days": random.choice([2, 3]),
        "budget": random.choice([2600, 3000, 3600]),
        "travelers": random.choice([1, 2]),
        "preferences": random.choice([["family"], ["budget"], ["comfort"], ["family", "budget"]]),
        "maxAgentSteps": 10,
        "maxToolCalls": 10,
        "allowedTools": ["search_hotels", "search_transports", "search_attractions"],
    }
    headers = {
        "X-Trace-Id": "trace-%s-%s" % (request_id, int(time.time() * 1000)),
        "X-Internal-Client-Id": internal_client_id,
        "X-Internal-Signature": _make_signature(idem, shared_secret),
    }
    start = time.perf_counter()
    try:
        response = requests.post(base_url.rstrip("/") + endpoint, json=payload, headers=headers, timeout=timeout_sec)
        elapsed = (time.perf_counter() - start) * 1000
        body = {}
        if response.status_code == 200:
            body = response.json()
        return {
            "ok": response.status_code == 200,
            "status": response.status_code,
            "latency_ms": elapsed,
            "agents": sorted(body.get("registered_agents", [])) if body else [],
            "tools": sorted(list(body.get("registered_tools", {}).keys())) if body else [],
        }
    except Exception:
        elapsed = (time.perf_counter() - start) * 1000
        return {"ok": False, "status": 0, "latency_ms": elapsed, "agents": [], "tools": []}


def run_mode(
    mode_label: str,
    base_url: str,
    endpoint: str,
    total_requests: int,
    concurrency: int,
    timeout_sec: int,
    shared_secret: str,
    internal_client_id: str,
) -> Dict[str, Any]:
    latencies: List[float] = []
    ok_count = 0
    status_hist: Dict[str, int] = {}
    agent_catalogs: Dict[str, int] = {}
    tool_catalogs: Dict[str, int] = {}
    lock = threading.Lock()

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [
            pool.submit(
                _single_call,
                base_url,
                endpoint,
                timeout_sec,
                index,
                shared_secret,
                internal_client_id,
            )
            for index in range(total_requests)
        ]
        for future in as_completed(futures):
            result = future.result()
            with lock:
                latencies.append(result["latency_ms"])
                if result["ok"]:
                    ok_count += 1
                status_key = str(result["status"])
                status_hist[status_key] = status_hist.get(status_key, 0) + 1
                if result["agents"]:
                    key = "|".join(result["agents"])
                    agent_catalogs[key] = agent_catalogs.get(key, 0) + 1
                if result["tools"]:
                    key = "|".join(result["tools"])
                    tool_catalogs[key] = tool_catalogs.get(key, 0) + 1

    latencies_sorted = sorted(latencies)
    p95 = latencies_sorted[int(len(latencies_sorted) * 0.95) - 1] if latencies_sorted else 0.0
    p99 = latencies_sorted[int(len(latencies_sorted) * 0.99) - 1] if latencies_sorted else 0.0
    top_agents = _top_catalog(agent_catalogs)
    top_tools = _top_catalog(tool_catalogs)
    return {
        "mode": mode_label,
        "base_url": base_url,
        "sample_size": total_requests,
        "success": ok_count,
        "error": total_requests - ok_count,
        "success_rate": round(ok_count / max(1, total_requests), 4),
        "avg_latency_ms": round(mean(latencies_sorted), 2) if latencies_sorted else 0.0,
        "p95_latency_ms": round(p95, 2),
        "p99_latency_ms": round(p99, 2),
        "status_histogram": status_hist,
        "registered_agents": top_agents,
        "registered_tools": top_tools,
        "agent_catalog_variants": len(agent_catalogs),
        "tool_catalog_variants": len(tool_catalogs),
        "missing_service_errors": status_hist.get("0", 0),
        "missing_tool_errors": status_hist.get("0", 0),
    }


def _top_catalog(rows: Dict[str, int]) -> List[str]:
    if not rows:
        return []
    top = sorted(rows.items(), key=lambda item: item[1], reverse=True)[0][0]
    if not top:
        return []
    return [part for part in top.split("|") if part]


def compare_reports(legacy: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    reasons: List[str] = []
    success_gap = abs(float(legacy.get("success_rate", 0.0)) - float(new.get("success_rate", 0.0)))
    if success_gap > 0.05:
        reasons.append("success_rate_gap_gt_0.05")

    if legacy.get("sample_size") != new.get("sample_size"):
        reasons.append("sample_size_mismatch")

    if legacy.get("missing_service_errors", 0) != new.get("missing_service_errors", 0):
        reasons.append("missing_service_errors_mismatch")

    if legacy.get("missing_tool_errors", 0) != new.get("missing_tool_errors", 0):
        reasons.append("missing_tool_errors_mismatch")

    legacy_agents = set(legacy.get("registered_agents", []))
    new_agents = set(new.get("registered_agents", []))
    if legacy_agents and new_agents and legacy_agents != new_agents:
        reasons.append("registered_agents_mismatch")

    legacy_tools = set(legacy.get("registered_tools", []))
    new_tools = set(new.get("registered_tools", []))
    if legacy_tools and new_tools and legacy_tools != new_tools:
        reasons.append("registered_tools_mismatch")

    return {
        "consistency_status": "pass" if not reasons else "fail",
        "fail_reasons": reasons,
        "success_rate_gap": round(success_gap, 4),
        "legacy_avg_latency_ms": legacy.get("avg_latency_ms", 0.0),
        "new_avg_latency_ms": new.get("avg_latency_ms", 0.0),
        "legacy_p95_latency_ms": legacy.get("p95_latency_ms", 0.0),
        "new_p95_latency_ms": new.get("p95_latency_ms", 0.0),
        "legacy_p99_latency_ms": legacy.get("p99_latency_ms", 0.0),
        "new_p99_latency_ms": new.get("p99_latency_ms", 0.0),
    }


def render_markdown_report(legacy: Dict[str, Any], new: Dict[str, Any], summary: Dict[str, Any]) -> str:
    lines = [
        "# Etcd Client Migration Canary Report",
        "",
        "## 1. Comparison Summary",
        "",
        "- Legacy mode: `%s`" % legacy.get("mode", "legacy"),
        "- New mode: `%s`" % new.get("mode", "new"),
        "- Consistency status: **%s**" % summary.get("consistency_status", "unknown"),
        "- Fail reasons: %s" % (", ".join(summary.get("fail_reasons", [])) if summary.get("fail_reasons") else "none"),
        "",
        "## 2. Metric Table",
        "",
        "| Metric | Legacy | New |",
        "|---|---:|---:|",
        "| success_rate | %s | %s |" % (legacy.get("success_rate", 0), new.get("success_rate", 0)),
        "| avg_latency_ms | %s | %s |" % (legacy.get("avg_latency_ms", 0), new.get("avg_latency_ms", 0)),
        "| p95_latency_ms | %s | %s |" % (legacy.get("p95_latency_ms", 0), new.get("p95_latency_ms", 0)),
        "| p99_latency_ms | %s | %s |" % (legacy.get("p99_latency_ms", 0), new.get("p99_latency_ms", 0)),
        "| missing_service_errors | %s | %s |" % (legacy.get("missing_service_errors", 0), new.get("missing_service_errors", 0)),
        "| missing_tool_errors | %s | %s |" % (legacy.get("missing_tool_errors", 0), new.get("missing_tool_errors", 0)),
        "",
        "## 3. Gate Decision",
        "",
    ]
    if summary.get("consistency_status") == "pass":
        lines.append("- ✅ Promote canary: consistency gate passed.")
    else:
        lines.append("- ❌ Hold rollout: consistency gate failed.")
    lines.extend(
        [
            "- Suggested actions:",
            "  1. Verify service/tool catalog parity.",
            "  2. Compare latency and error histogram drift.",
            "  3. Re-run canary after fix before full rollout.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Dual-stack etcd migration drill with canary comparison")
    parser.add_argument("--legacy-base-url", default="http://localhost:8000", help="Legacy deployment base url")
    parser.add_argument("--new-base-url", default="http://localhost:8001", help="New deployment base url")
    parser.add_argument("--endpoint", default="/runtime/recommend", help="Runtime endpoint path")
    parser.add_argument("--requests", type=int, default=100, help="Request count per mode")
    parser.add_argument("--concurrency", type=int, default=20, help="Concurrent workers")
    parser.add_argument("--timeout", type=int, default=8, help="Request timeout seconds")
    parser.add_argument("--shared-secret", default="demo-internal-secret", help="Internal shared secret")
    parser.add_argument("--internal-client-id", default="spring-gateway", help="Internal client id")
    parser.add_argument("--out-json", default="stress/etcd_migration_compare.json", help="JSON output path")
    parser.add_argument("--out-md", default="stress/etcd_canary_report.md", help="Markdown report path")
    args = parser.parse_args()

    legacy = run_mode(
        "legacy",
        args.legacy_base_url,
        args.endpoint,
        args.requests,
        args.concurrency,
        args.timeout,
        args.shared_secret,
        args.internal_client_id,
    )
    new = run_mode(
        "new",
        args.new_base_url,
        args.endpoint,
        args.requests,
        args.concurrency,
        args.timeout,
        args.shared_secret,
        args.internal_client_id,
    )
    summary = compare_reports(legacy, new)

    output = {"legacy": legacy, "new": new, "summary": summary, "timestamp": int(time.time())}
    with open(args.out_json, "w", encoding="utf-8") as file:
        json.dump(output, file, ensure_ascii=False, indent=2)

    markdown = render_markdown_report(legacy, new, summary)
    with open(args.out_md, "w", encoding="utf-8") as file:
        file.write(markdown)

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
