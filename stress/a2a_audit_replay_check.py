"""Module provides service components and helpers."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional


def run(
    path: Path,
    window_minutes: Optional[int] = None,
    from_ts: Optional[str] = None,
    to_ts: Optional[str] = None,
    max_duplicates: int = 0,
) -> Dict[str, object]:
    if not path.exists():
        return {"ok": False, "reason": "file-not-found", "path": str(path)}

    total = 0
    filtered_out = 0
    duplicates = 0
    seen_ids = set()
    topics: Dict[str, int] = {}

    start_time, end_time = _resolve_window(window_minutes, from_ts, to_ts)

    with path.open("r", encoding="utf-8") as fp:
        for line in fp:
            text = line.strip()
            if not text:
                continue
            total += 1
            try:
                row = json.loads(text)
            except Exception:
                continue
            topic = str(row.get("topic", ""))
            if not _in_window(row.get("ts"), start_time, end_time):
                filtered_out += 1
                continue
            topics[topic] = topics.get(topic, 0) + 1
            payload = row.get("payload", {})
            if isinstance(payload, dict):
                msg_id = str(payload.get("id", ""))
                if msg_id:
                    if msg_id in seen_ids:
                        duplicates += 1
                    else:
                        seen_ids.add(msg_id)

    gate_pass = duplicates <= max(0, max_duplicates)
    return {
        "ok": True,
        "path": str(path),
        "total": total,
        "filtered_out": filtered_out,
        "unique_ids": len(seen_ids),
        "duplicate_ids": duplicates,
        "max_duplicates": max_duplicates,
        "gate_pass": gate_pass,
        "window_start": start_time.isoformat() if start_time else None,
        "window_end": end_time.isoformat() if end_time else None,
        "topics": topics,
    }


def _resolve_window(
    window_minutes: Optional[int],
    from_ts: Optional[str],
    to_ts: Optional[str],
) -> tuple[Optional[datetime], Optional[datetime]]:
    start = _parse_ts(from_ts) if from_ts else None
    end = _parse_ts(to_ts) if to_ts else None
    if window_minutes is not None and window_minutes > 0 and start is None and end is None:
        end = datetime.now(timezone.utc)
        start = end - timedelta(minutes=window_minutes)
    return start, end


def _parse_ts(value: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _in_window(value: object, start: Optional[datetime], end: Optional[datetime]) -> bool:
    if start is None and end is None:
        return True
    if not isinstance(value, str):
        return False
    ts = _parse_ts(value)
    if ts is None:
        return False
    if start is not None and ts < start:
        return False
    if end is not None and ts > end:
        return False
    return True


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Replay-check A2A audit mirror events")
    parser.add_argument("--file", default="var/events/a2a_audit_events.jsonl", help="A2A audit JSONL file")
    parser.add_argument("--window-minutes", type=int, default=None, help="Only check records in latest N minutes")
    parser.add_argument("--from-ts", type=str, default=None, help="Inclusive ISO timestamp lower bound")
    parser.add_argument("--to-ts", type=str, default=None, help="Inclusive ISO timestamp upper bound")
    parser.add_argument("--max-duplicates", type=int, default=0, help="Maximum allowed duplicate message IDs")
    args = parser.parse_args()
    report = run(
        Path(args.file),
        window_minutes=args.window_minutes,
        from_ts=args.from_ts,
        to_ts=args.to_ts,
        max_duplicates=args.max_duplicates,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not bool(report.get("gate_pass", True)):
        raise SystemExit(2)


if __name__ == "__main__":
    main()

