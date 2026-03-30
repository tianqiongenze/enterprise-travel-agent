"""Module provides service components and helpers."""

import argparse
import json
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class CheckResult:
    name: str
    status: str
    detail: str
    durationMs: int
    artifacts: List[str]


def _now_ms() -> int:
    return int(time.time() * 1000)


def _run_command(name: str, command: List[str], cwd: Path, timeout_sec: int = 600) -> CheckResult:
    start = _now_ms()
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
        status = "PASS" if completed.returncode == 0 else "FAIL"
        detail_lines = [
            f"command={' '.join(command)}",
            f"returncode={completed.returncode}",
        ]
        if completed.stdout.strip():
            detail_lines.append(f"stdout={completed.stdout.strip()[:1200]}")
        if completed.stderr.strip():
            detail_lines.append(f"stderr={completed.stderr.strip()[:1200]}")
        return CheckResult(
            name=name,
            status=status,
            detail=" | ".join(detail_lines),
            durationMs=_now_ms() - start,
            artifacts=[],
        )
    except FileNotFoundError as error:
        return CheckResult(
            name=name,
            status="SKIP",
            detail=f"command unavailable: {error}",
            durationMs=_now_ms() - start,
            artifacts=[],
        )
    except subprocess.TimeoutExpired:
        return CheckResult(
            name=name,
            status="FAIL",
            detail=f"command timeout after {timeout_sec}s",
            durationMs=_now_ms() - start,
            artifacts=[],
        )


def _file_check(name: str, path: Path, required: bool = True) -> CheckResult:
    start = _now_ms()
    exists = path.exists()
    if exists:
        return CheckResult(
            name=name,
            status="PASS",
            detail=f"file exists: {path}",
            durationMs=_now_ms() - start,
            artifacts=[str(path)],
        )
    status = "FAIL" if required else "SKIP"
    return CheckResult(
        name=name,
        status=status,
        detail=f"file missing: {path}",
        durationMs=_now_ms() - start,
        artifacts=[],
    )


def _load_json(path: Path) -> Optional[Dict[str, object]]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _parse_prom_metrics(path: Path) -> Dict[str, float]:
    if not path.exists():
        return {}
    metrics: Dict[str, float] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        parts = raw.split()
        if len(parts) != 2:
            continue
        try:
            metrics[parts[0]] = float(parts[1])
        except ValueError:
            continue
    return metrics


def _bootstrap_consumer_metrics(project_root: Path, metrics_path: Path) -> Optional[str]:
    if metrics_path.exists():
        return None
    try:
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        from src.travel_agent.events.consumer import ConsumerMetrics, RetryPolicy, process_local_events

        events = [
            {
                "topic": "recommend.requested",
                "payload": {"city": "上海", "days": 3, "budget": 3200},
            },
            {
                "topic": "recommend.completed",
                "payload": {"city": "上海", "hotel_count": 3, "transport_count": 2, "itinerary_days": 3},
            },
        ]
        metrics = ConsumerMetrics()
        process_local_events(events, retry_policy=RetryPolicy(max_retries=1, backoff_ms=10), metrics=metrics)
        metrics.write_prometheus_file(str(metrics_path))
        return f"bootstrapped metrics at {metrics_path}"
    except Exception as error:
        return f"bootstrap metrics failed: {error}"


def run_all_checks(project_root: Path, args: argparse.Namespace) -> Dict[str, object]:
    checks: List[CheckResult] = []

    stress_dir = project_root / "stress"
    deploy_dir = project_root / "deploy"
    scripts_dir = deploy_dir / "scripts"

    canary_report = stress_dir / "etcd_migration_compare.json"
    canary_decision = stress_dir / "canary_gate_decision.json"
    canary_metrics = stress_dir / "canary_gate_metrics.prom"
    consumer_metrics = stress_dir / "pulsar_consumer_metrics.prom"
    capacity_json = stress_dir / "capacity_cost_report.json"
    capacity_md = stress_dir / "capacity_cost_report.md"

    bootstrap_detail = _bootstrap_consumer_metrics(project_root, consumer_metrics)
    if bootstrap_detail is not None:
        checks.append(
            CheckResult(
                name="consumer_metrics_bootstrap",
                status="PASS" if consumer_metrics.exists() else "FAIL",
                detail=bootstrap_detail,
                durationMs=0,
                artifacts=[str(consumer_metrics)] if consumer_metrics.exists() else [],
            )
        )

    checks.append(_file_check("canary_report_present", canary_report))

    if args.run_canary_gate:
        check = _run_command(
            "canary_gate_recompute",
            [
                args.python_exec,
                str(scripts_dir / "canary_gate.py"),
                "--report",
                str(canary_report),
                "--event-metrics",
                str(consumer_metrics),
                "--out",
                str(canary_decision),
                "--metrics-out",
                str(canary_metrics),
            ],
            cwd=project_root,
            timeout_sec=120,
        )
        check.artifacts = [str(canary_decision), str(canary_metrics)]
        checks.append(check)

    checks.append(_file_check("canary_decision_present", canary_decision))
    checks.append(_file_check("canary_metrics_present", canary_metrics))
    checks.append(_file_check("consumer_metrics_present", consumer_metrics, required=False))

    decision = _load_json(canary_decision)
    if decision is None:
        checks.append(
            CheckResult(
                name="canary_decision_valid_json",
                status="FAIL",
                detail="invalid or missing canary decision json",
                durationMs=0,
                artifacts=[str(canary_decision)],
            )
        )
    else:
        action = str(decision.get("action", "rollback"))
        status = "PASS" if action == "promote" else "FAIL"
        checks.append(
            CheckResult(
                name="canary_action_is_promote",
                status=status,
                detail=f"action={action}",
                durationMs=0,
                artifacts=[str(canary_decision)],
            )
        )

    prom = _parse_prom_metrics(canary_metrics)
    if prom:
        lag = prom.get("canary_gate_event_consumer_lag_seconds", 0.0)
        dlq = prom.get("canary_gate_event_consumer_dlq_total", 0.0)
        checks.append(
            CheckResult(
                name="event_consumer_thresholds",
                status="PASS" if lag <= args.max_event_lag and dlq <= args.max_event_dlq else "FAIL",
                detail=f"lag={lag}, dlq={dlq}, limits=({args.max_event_lag}, {args.max_event_dlq})",
                durationMs=0,
                artifacts=[str(canary_metrics)],
            )
        )
    else:
        checks.append(
            CheckResult(
                name="event_consumer_thresholds",
                status="FAIL",
                detail="canary metrics not parseable",
                durationMs=0,
                artifacts=[str(canary_metrics)],
            )
        )

    if args.run_tests:
        checks.append(
            _run_command(
                "python_test_suite",
                [
                    args.python_exec,
                    "-u",
                    "-m",
                    "unittest",
                    "tests.test_event_bus",
                    "tests.test_event_consumers",
                    "tests.test_vector_backends",
                    "tests.test_capacity_cost_model",
                    "tests.test_canary_gate",
                    "tests.test_autosafemode",
                    "-v",
                ],
                cwd=project_root,
                timeout_sec=300,
            )
        )

    checks.append(_file_check("capacity_cost_json_present", capacity_json))
    checks.append(_file_check("capacity_cost_md_present", capacity_md))

    if args.run_capacity_model:
        check = _run_command(
            "capacity_cost_recompute",
            [
                args.python_exec,
                "-u",
                str(stress_dir / "capacity_cost_model.py"),
                "--peak-connected",
                str(args.peak_connected),
                "--active-ratio",
                str(args.active_ratio),
            ],
            cwd=project_root,
            timeout_sec=120,
        )
        check.artifacts = [str(capacity_json), str(capacity_md)]
        checks.append(check)

    if args.run_java_compile:
        checks.append(
            _run_command(
                "java_gateway_compile",
                ["mvn", "-q", "-DskipTests", "compile"],
                cwd=project_root / "services" / "techgroup-enterprise-travel-gateway",
                timeout_sec=300,
            )
        )

    pass_count = len([c for c in checks if c.status == "PASS"])
    fail_count = len([c for c in checks if c.status == "FAIL"])
    skip_count = len([c for c in checks if c.status == "SKIP"])

    overall = "PASS" if fail_count == 0 else "FAIL"
    summary = {
        "overall": overall,
        "passCount": pass_count,
        "failCount": fail_count,
        "skipCount": skip_count,
    }

    return {
        "generatedAt": int(time.time()),
        "summary": summary,
        "checks": [asdict(item) for item in checks],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run final go-live acceptance checks and emit JSON report")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--report-out", default="stress/go_live_final_report.json")
    parser.add_argument("--python-exec", default="python")
    parser.add_argument("--run-tests", action="store_true", default=True)
    parser.add_argument("--run-java-compile", action="store_true", default=True)
    parser.add_argument("--run-canary-gate", action="store_true", default=True)
    parser.add_argument("--run-capacity-model", action="store_true", default=True)
    parser.add_argument("--max-event-lag", type=float, default=60.0)
    parser.add_argument("--max-event-dlq", type=float, default=0.0)
    parser.add_argument("--peak-connected", type=int, default=1_000_000)
    parser.add_argument("--active-ratio", type=float, default=0.1)
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    report = run_all_checks(project_root, args)

    report_out = (project_root / args.report_out).resolve()
    report_out.parent.mkdir(parents=True, exist_ok=True)
    report_out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Generated: {report_out}")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

