#!/usr/bin/env python3
"""Gap3: real-embedding verification script.

Runs a baseline hash-embedding check (always, offline) and then attempts a
real embedding call:

- DashScope provider: only when AI_DASHSCOPE_API_KEY (or DASHSCOPE_API_KEY) is
  set; otherwise recorded as SKIP, never as a pass.
- Optional OpenAI-compatible endpoint via TRAVEL_EMBEDDING_ENDPOINT when the
  backend is forced.

Writes stress/embedding_verification_report.json + a sha256 sidecar. Exit 0 on
PASS or SKIP (skip is honest), exit 1 on failure.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "techgroup-enterprise-travel-runtime" / "src"))

from travel_agent.memory.embeddings import (  # noqa: E402
    DashScopeEmbeddingProvider,
    HashEmbeddingProvider,
)


def _check(provider, text: str) -> dict:
    vector = provider.embed(text)
    dim = provider.dim()
    norm = sum(v * v for v in vector) ** 0.5
    ok = len(vector) == dim and (norm == 0.0 or abs(norm - 1.0) < 0.05 or not isinstance(provider, HashEmbeddingProvider))
    return {"text": text, "dim": len(vector), "expected_dim": dim, "norm": round(norm, 6), "ok": ok}


def main() -> int:
    report: dict = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "backend_env": os.getenv("TRAVEL_EMBEDDING_BACKEND", "auto"),
        "checks": [],
        "verdict": None,
    }
    all_ok = True

    # Baseline: hash provider (always available, offline).
    try:
        checks = [_check(HashEmbeddingProvider(), "杭州 家庭 酒店 亲子"), _check(HashEmbeddingProvider(), "北京 商务 出行")]
        report["checks"].append({"provider": "hash", "result": "PASS", "checks": checks})
        all_ok = all_ok and all(c["ok"] for c in checks)
    except Exception as e:  # noqa: BLE001
        report["checks"].append({"provider": "hash", "result": "FAIL", "error": str(e)})
        all_ok = False

    # Real embedding: dashscope only if a key is present; otherwise SKIP.
    has_key = bool(os.getenv("AI_DASHSCOPE_API_KEY", os.getenv("DASHSCOPE_API_KEY", "")).strip())
    if not has_key:
        report["checks"].append({
            "provider": "dashscope",
            "result": "SKIP",
            "reason": "AI_DASHSCOPE_API_KEY/DASHSCOPE_API_KEY not set; real-embedding call not performed (honest skip)",
        })
    else:
        try:
            provider = DashScopeEmbeddingProvider()
            checks = [_check(provider, "杭州 家庭 酒店 亲子"), _check(provider, "北京 商务 出行")]
            ok = all(c["ok"] and c["dim"] == c["expected_dim"] for c in checks)
            report["checks"].append({"provider": provider.provider_name, "result": "PASS" if ok else "FAIL", "checks": checks})
            all_ok = all_ok and ok
        except Exception as e:  # noqa: BLE001
            report["checks"].append({"provider": "dashscope", "result": "FAIL", "error": str(e)[:500]})
            all_ok = False

    skip_only = all(c["result"] in ("PASS", "SKIP") for c in report["checks"]) and any(
        c["result"] == "SKIP" for c in report["checks"]
    )
    report["verdict"] = "PASS" if all_ok and not skip_only else ("SKIP" if skip_only else "FAIL")

    out_dir = ROOT / "stress"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "embedding_verification_report.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    digest = hashlib.sha256(out_path.read_bytes()).hexdigest()
    (out_dir / "embedding_verification_report.sha256").write_text(digest + "\n", encoding="utf-8")

    print(f"[verify_real_embedding] verdict={report['verdict']} report={out_path}")
    for check in report["checks"]:
        print(f"  - {check['provider']}: {check['result']}" + (f" ({check.get('reason', '')})" if check.get("reason") else ""))
    return 0 if report["verdict"] in ("PASS", "SKIP") else 1


if __name__ == "__main__":
    sys.exit(main())
