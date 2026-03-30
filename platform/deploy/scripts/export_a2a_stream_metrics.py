"""Module provides service components and helpers."""

import os
import time
from pathlib import Path
from typing import Any, Iterable, cast


def collect_and_write_metrics() -> Path:
    import redis

    redis_url = os.getenv("TRAVEL_A2A_REDIS_URL", os.getenv("TRAVEL_REDIS_URL", "redis://127.0.0.1:7000"))
    key_prefix = os.getenv("TRAVEL_A2A_KEY_PREFIX", "a2a:stream")
    group = os.getenv("TRAVEL_A2A_STREAM_GROUP", "a2a-consumers")
    out_path = Path(os.getenv("TRAVEL_A2A_METRICS_PATH", "stress/a2a_stream_metrics.prom"))
    day_slot = os.getenv("TRAVEL_A2A_METRICS_DAY", "")
    if not day_slot:
        day_slot = time.strftime("%Y%m%d")

    client = redis.Redis.from_url(redis_url, decode_responses=True)
    raw_keys = client.keys(f"{key_prefix}:*:{day_slot}")
    if hasattr(raw_keys, "__await__"):
        raise RuntimeError("sync redis client expected; got awaitable keys result")
    keys = [str(item) for item in cast(Iterable[Any], raw_keys)]

    pending_total = 0
    max_lag_ms = 0
    streams_total = 0

    for key in keys:
        streams_total += 1
        try:
            summary = client.xpending(key, group)
            # redis-py returns dict on modern versions.
            if isinstance(summary, dict):
                pending = int(summary.get("pending", 0))
                pending_total += pending
                min_id = str(summary.get("min", ""))
                max_id = str(summary.get("max", ""))
                if min_id and "-" in min_id and max_id and "-" in max_id:
                    try:
                        min_ms = int(min_id.split("-")[0])
                        max_ms = int(max_id.split("-")[0])
                        max_lag_ms = max(max_lag_ms, max_ms - min_ms)
                    except Exception:
                        pass
        except Exception:
            continue

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        "\n".join(
            [
                f"travel_a2a_streams_total {streams_total}",
                f"travel_a2a_stream_pending_total {pending_total}",
                f"travel_a2a_stream_lag_ms {max_lag_ms}",
                f"travel_a2a_stream_metrics_timestamp {time.time()}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return out_path


def main() -> None:
    out_path = collect_and_write_metrics()
    print(f"metrics_path={out_path}")


if __name__ == "__main__":
    main()

