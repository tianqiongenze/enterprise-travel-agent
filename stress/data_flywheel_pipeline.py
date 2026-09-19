"""Local data-flywheel pipeline: events -> bronze/silver/gold artifacts.

This provides a runnable enterprise-style scaffold for Iceberg/Flink adoption.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List


def read_jsonl(path: Path) -> List[Dict[str, object]]:
    if not path.exists():
        return []
    rows: List[Dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                rows.append(parsed)
        except Exception:
            continue
    return rows


def write_jsonl(path: Path, rows: Iterable[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def normalize_event(row: Dict[str, object]) -> Dict[str, object]:
    topic = str(row.get("topic", "unknown"))
    payload = row.get("payload", {})
    if not isinstance(payload, dict):
        payload = {"raw": str(payload)}
    city = str(payload.get("city", "unknown"))
    ts = _to_epoch_seconds(row.get("ts", time.time()))
    normalized = {
        "topic": topic,
        "city": city,
        "ts": ts,
        "payload": payload,
        "event_date": time.strftime("%Y-%m-%d", time.localtime(ts)),
    }
    normalized["event_id"] = _event_id(normalized)
    return normalized


def _event_id(row: Dict[str, object]) -> str:
    raw = json.dumps(
        {
            "topic": row.get("topic"),
            "city": row.get("city"),
            "ts": row.get("ts"),
            "payload": row.get("payload"),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _to_epoch_seconds(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return time.time()
    try:
        return float(text)
    except ValueError:
        pass
    try:
        normalized = text.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except ValueError:
        return time.time()


def build_city_features(rows: List[Dict[str, object]]) -> List[Dict[str, object]]:
    topic_counter_by_city: Dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        city = str(row.get("city", "unknown"))
        topic = str(row.get("topic", "unknown"))
        topic_counter_by_city[city][topic] += 1

    out: List[Dict[str, object]] = []
    for city, counter in topic_counter_by_city.items():
        requested = int(counter.get("recommend.requested", 0))
        completed = int(counter.get("recommend.completed", 0))
        conversion = (completed / requested) if requested > 0 else 0.0
        out.append(
            {
                "city": city,
                "requested": requested,
                "completed": completed,
                "completion_ratio": round(conversion, 6),
                "feature_ts": int(time.time()),
            }
        )
    out.sort(key=lambda item: str(item.get("city", "")))
    return out


def build_top_topics(rows: List[Dict[str, object]]) -> List[Dict[str, object]]:
    counter: Counter[str] = Counter()
    for row in rows:
        counter[str(row.get("topic", "unknown"))] += 1
    return [{"topic": key, "count": count} for key, count in counter.most_common(20)]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local data-flywheel pipeline")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--events", default="var/events/audit_events.jsonl")
    parser.add_argument("--out-root", default="var/lakehouse")
    parser.add_argument("--state-file", default="var/lakehouse/flywheel_state.json")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    events_path = (root / args.events).resolve()
    out_root = (root / args.out_root).resolve()

    source_rows = read_jsonl(events_path)
    normalized = [normalize_event(row) for row in source_rows]

    state_file = (root / args.state_file).resolve()
    state = {}
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
        except Exception:
            state = {}
    seen = set(state.get("seen_event_ids", [])) if isinstance(state, dict) else set()
    deduped: List[Dict[str, object]] = []
    duplicate_count = 0
    for row in normalized:
        event_id = str(row.get("event_id", ""))
        if event_id and event_id in seen:
            duplicate_count += 1
            continue
        if event_id:
            seen.add(event_id)
        deduped.append(row)

    bronze_path = out_root / "bronze" / "travel_events.jsonl"
    silver_path = out_root / "silver" / "travel_events_clean.jsonl"
    features_path = out_root / "gold" / "city_features.jsonl"
    topics_path = out_root / "gold" / "top_topics.jsonl"

    write_jsonl(bronze_path, source_rows)
    write_jsonl(silver_path, deduped)
    write_jsonl(features_path, build_city_features(deduped))
    write_jsonl(topics_path, build_top_topics(deduped))

    manifest = {
        "generatedAt": int(time.time()),
        "source": str(events_path.relative_to(root)) if events_path.exists() else str(events_path),
        "recordsIn": len(source_rows),
        "recordsNormalized": len(normalized),
        "recordsDeduped": len(deduped),
        "duplicateDropped": duplicate_count,
        "artifacts": [
            str(bronze_path.relative_to(root)),
            str(silver_path.relative_to(root)),
            str(features_path.relative_to(root)),
            str(topics_path.relative_to(root)),
        ],
        "pass": len(normalized) >= 0,
    }
    manifest_path = out_root / "flywheel_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(
        json.dumps(
            {
                "updatedAt": int(time.time()),
                "seen_event_ids": list(seen)[-100000:],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"Generated: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

