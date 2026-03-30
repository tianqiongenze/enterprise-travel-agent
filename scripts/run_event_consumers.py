"""Module provides service components and helpers."""

import argparse
import os
import sys
import threading
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.travel_agent.events.consumer import PulsarConsumerRunner
from deploy.scripts.export_a2a_stream_metrics import collect_and_write_metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Pulsar event consumers for audit/profile/notification pipelines")
    parser.add_argument("--max-messages", type=int, default=0, help="Stop after processing N messages (0 means run forever)")
    parser.add_argument("--max-retries", type=int, default=None, help="Override TRAVEL_EVENT_CONSUMER_MAX_RETRIES")
    parser.add_argument("--retry-backoff-ms", type=int, default=None, help="Override TRAVEL_EVENT_CONSUMER_RETRY_BACKOFF_MS")
    parser.add_argument("--topic", type=str, default=None, help="Override TRAVEL_PULSAR_CONSUME_TOPIC")
    parser.add_argument(
        "--export-a2a-metrics-every-sec",
        type=int,
        default=0,
        help="If >0, periodically export A2A stream metrics while consumer is running",
    )
    args = parser.parse_args()

    if args.max_retries is not None:
        os.environ["TRAVEL_EVENT_CONSUMER_MAX_RETRIES"] = str(args.max_retries)
    if args.retry_backoff_ms is not None:
        os.environ["TRAVEL_EVENT_CONSUMER_RETRY_BACKOFF_MS"] = str(args.retry_backoff_ms)
    if args.topic:
        os.environ["TRAVEL_PULSAR_CONSUME_TOPIC"] = args.topic

    strict = os.getenv("TRAVEL_EVENT_BUS_STRICT", "false").strip().lower() == "true"
    runner = None
    stop_event = threading.Event()
    metrics_thread = None

    def _metrics_loop(interval: int) -> None:
        while not stop_event.is_set():
            try:
                collect_and_write_metrics()
            except Exception:
                pass
            stop_event.wait(max(1, interval))

    try:
        if args.export_a2a_metrics_every_sec > 0:
            metrics_thread = threading.Thread(
                target=_metrics_loop,
                args=(args.export_a2a_metrics_every_sec,),
                daemon=True,
            )
            metrics_thread.start()
        runner = PulsarConsumerRunner()
        processed = runner.run(max_messages=args.max_messages)
        print(f"processed={processed}")
        print(f"metrics_path={os.getenv('TRAVEL_EVENT_METRICS_PATH', 'stress/pulsar_consumer_metrics.prom')}")
    except Exception as error:
        if strict:
            raise
        print(f"[event-consumer] pulsar consumer unavailable: {error}")
    finally:
        stop_event.set()
        if metrics_thread is not None and metrics_thread.is_alive():
            metrics_thread.join(timeout=1)
        if args.export_a2a_metrics_every_sec > 0:
            try:
                final_path = collect_and_write_metrics()
                print(f"a2a_metrics_path={final_path}")
            except Exception:
                pass
        if runner is not None:
            runner.close()


if __name__ == "__main__":
    main()

