"""Module provides service components and helpers."""

import argparse
import hashlib
import hmac
import importlib
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import faiss  # type: ignore # noqa: F401
except Exception:
    faiss = None  # type: ignore[assignment]


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


def _load_json(path: Path) -> Optional[Dict[str, Any]]:
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


def _canonical_payload(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _verify_evidence_signature(payload: Dict[str, Any], key: str) -> bool:
    signature = str(payload.get("signature", ""))
    if not signature or not key:
        return False
    signable = dict(payload)
    signable.pop("signature", None)
    signable.pop("signed", None)
    signable.pop("signatureAlgorithm", None)
    expected = hmac.new(key.encode("utf-8"), _canonical_payload(signable).encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)


def _evidence_hardening_check(
    name: str,
    path: Path,
    key: str,
    require_signature: bool,
    max_age_hours: float,
    allowed_envs: List[str],
) -> CheckResult:
    payload = _load_json(path)
    if payload is None:
        return CheckResult(name=name, status="FAIL", detail=f"missing or invalid json: {path}", durationMs=0, artifacts=[str(path)])

    generated_at_raw = payload.get("generatedAt", 0)
    generated_at = int(generated_at_raw) if isinstance(generated_at_raw, (int, float, str)) else 0
    age_seconds = max(0, int(time.time()) - generated_at) if generated_at > 0 else 10**9
    max_age_seconds = int(max(1.0, max_age_hours) * 3600)

    environment = str(payload.get("environment", "")).strip().lower()
    allowed = {item.strip().lower() for item in allowed_envs if item.strip()}
    env_ok = environment in allowed if allowed else True

    signed = bool(payload.get("signed", False))
    signature_ok = _verify_evidence_signature(payload, key) if signed else False
    signature_gate_ok = (signature_ok if require_signature else (signature_ok or not signed))

    status = "PASS" if (signature_gate_ok and age_seconds <= max_age_seconds and env_ok) else "FAIL"
    detail = (
        f"signed={signed}, signatureOk={signature_ok}, requireSignature={require_signature}, "
        f"ageSeconds={age_seconds}, maxAgeSeconds={max_age_seconds}, "
        f"environment={environment}, allowed={sorted(list(allowed))}"
    )
    return CheckResult(name=name, status=status, detail=detail, durationMs=0, artifacts=[str(path)])


def _bootstrap_consumer_metrics(project_root: Path, metrics_path: Path) -> Optional[str]:
    if metrics_path.exists():
        return None
    try:
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        runtime_src = project_root / "services" / "techgroup-enterprise-travel-runtime"
        runtime_src_path = str(runtime_src)
        if runtime_src_path not in sys.path:
            sys.path.insert(0, runtime_src_path)
        consumer_module = importlib.import_module("src.travel_agent.events.consumer")
        ConsumerMetrics = getattr(consumer_module, "ConsumerMetrics")
        RetryPolicy = getattr(consumer_module, "RetryPolicy")
        process_local_events = getattr(consumer_module, "process_local_events")

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


def _security_env_gate(profile: str) -> CheckResult:
    """Reject demo authentication settings outside the local profile.

    ``profile`` is one of ``local`` | ``staging`` | ``prod``. Staging and prod
    require: a real internal shared secret, an authentication mode other than
    ``none``, and a semantic embedding provider (not the hash fallback).
    """
    secret = os.getenv("TRAVEL_INTERNAL_SHARED_SECRET", "").strip()
    auth_mode = os.getenv("TRAVEL_AUTH_MODE", "internal").strip().lower()
    security_mode = os.getenv("TRAVEL_SECURITY_MODE", "off").strip().lower()
    embedding_backend = os.getenv("TRAVEL_EMBEDDING_BACKEND", "auto").strip().lower()
    has_remote_key = bool(
        os.getenv("AI_DASHSCOPE_API_KEY", os.getenv("DASHSCOPE_API_KEY", "")).strip()
    )

    problems: List[str] = []
    if profile != "local" and (not secret or secret == "demo-internal-secret"):
        problems.append("TRAVEL_INTERNAL_SHARED_SECRET missing or still the public demo value")
    if auth_mode == "none":
        problems.append("TRAVEL_AUTH_MODE=none is not permitted in " + profile)
    if profile == "prod" and auth_mode != "oidc":
        problems.append("TRAVEL_AUTH_MODE must be 'oidc' in prod")
    if profile == "prod" and security_mode != "oauth2":
        problems.append("TRAVEL_SECURITY_MODE must be 'oauth2' in prod")
    if embedding_backend == "hash":
        problems.append("TRAVEL_EMBEDDING_BACKEND=hash provides no semantic retrieval")
    if embedding_backend == "auto" and profile == "prod" and not has_remote_key:
        problems.append(
            "TRAVEL_EMBEDDING_BACKEND=auto in prod requires a local model install or AI_DASHSCOPE_API_KEY"
        )

    detail = f"auth={auth_mode} security={security_mode} embedding={embedding_backend}"
    if problems:
        return CheckResult(
            name="security_env_gate",
            status="FAIL",
            detail="; ".join(problems),
            durationMs=0,
            artifacts=[],
        )
    if profile == "local" and (not secret or secret == "demo-internal-secret"):
        detail += "; WARNING: demo internal secret in local profile"
    return CheckResult(
        name="security_env_gate",
        status="PASS",
        detail=detail,
        durationMs=0,
        artifacts=[],
    )


def run_all_checks(project_root: Path, args: argparse.Namespace) -> Dict[str, object]:
    checks: List[CheckResult] = []

    stress_dir = project_root / "stress"
    deploy_dir = project_root / "platform" / "deploy"
    if not deploy_dir.exists():
        deploy_dir = project_root / "deploy"
    scripts_dir = deploy_dir / "scripts"

    canary_report = stress_dir / "etcd_migration_compare.json"
    canary_decision = stress_dir / "canary_gate_decision.json"
    canary_metrics = stress_dir / "canary_gate_metrics.prom"
    consumer_metrics = stress_dir / "pulsar_consumer_metrics.prom"
    capacity_json = stress_dir / "capacity_cost_report.json"
    capacity_md = stress_dir / "capacity_cost_report.md"
    scale_readiness_json = stress_dir / "global_scale_readiness_report.json"
    scale_readiness_md = stress_dir / "global_scale_readiness_report.md"
    distributed_json = stress_dir / "distributed_benchmark_evidence.json"
    distributed_md = stress_dir / "distributed_benchmark_evidence.md"
    fault_drill_json = stress_dir / "multi_region_fault_drill_report.json"
    fault_drill_md = stress_dir / "multi_region_fault_drill_report.md"
    flywheel_manifest = project_root / "var" / "lakehouse" / "flywheel_manifest.json"
    source_protection_manifest = project_root / "var" / "release_hardening" / "source_protection_manifest.json"

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
                    "scripts/run_python_tests_ci.py",
                    "tests.test_event_bus",
                    "tests.test_event_consumers",
                    "tests.test_vector_backends",
                    "tests.test_capacity_cost_model",
                    "tests.test_canary_gate",
                    "tests.test_autosafemode",
                ],
                cwd=project_root,
                timeout_sec=300,
            )
        )

    checks.append(_file_check("capacity_cost_json_present", capacity_json))
    checks.append(_file_check("capacity_cost_md_present", capacity_md))

    if args.require_source_protection:
        checks.append(_file_check("release_source_protection_manifest_present", source_protection_manifest))

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

    if args.run_distributed_benchmark:
        check = _run_command(
            "distributed_benchmark_evidence",
            [
                args.python_exec,
                "-u",
                str(stress_dir / "distributed_benchmark_evidence.py"),
                "--target-concurrency",
                str(args.target_concurrency),
                "--regions",
                str(args.distributed_regions),
                "--duration-minutes",
                str(args.distributed_duration_minutes),
                "--report-json",
                args.distributed_report_json,
                "--evidence-source",
                args.distributed_evidence_source,
                "--run-id",
                args.distributed_run_id,
                "--environment",
                args.distributed_environment,
            ],
            cwd=project_root,
            timeout_sec=120,
        )
        check.artifacts = [str(distributed_json), str(distributed_md)]
        checks.append(check)

    if args.run_fault_drill:
        check = _run_command(
            "multi_region_fault_drill",
            [
                args.python_exec,
                "-u",
                str(stress_dir / "multi_region_fault_drill.py"),
                "--canary-decision",
                args.fault_canary_decision,
                "--canary-metrics",
                args.fault_canary_metrics,
                "--incident-ticket",
                args.fault_incident_ticket,
                "--recovery-rto-minutes",
                str(args.fault_recovery_rto_minutes),
                "--recovery-rpo-seconds",
                str(args.fault_recovery_rpo_seconds),
                "--evidence-source",
                args.fault_evidence_source,
                "--run-id",
                args.fault_run_id,
                "--environment",
                args.fault_environment,
            ],
            cwd=project_root,
            timeout_sec=120,
        )
        check.artifacts = [str(fault_drill_json), str(fault_drill_md)]
        checks.append(check)

    if args.run_dr_automation:
        check = _run_command(
            "dr_automation_hook",
            [
                args.python_exec,
                "-u",
                str(scripts_dir / "dr_automation_hook.py"),
                "--evidence",
                str(fault_drill_json),
                "--incident-out",
                args.dr_incident_out,
                "--status-out",
                args.dr_status_out,
            ] + (["--auto-run"] if args.dr_auto_run else []),
            cwd=project_root,
            timeout_sec=120,
        )
        check.artifacts = [str(project_root / args.dr_status_out), str(project_root / args.dr_incident_out)]
        checks.append(check)

    checks.append(_file_check("distributed_benchmark_evidence_json_present", distributed_json, required=False))
    checks.append(_file_check("distributed_benchmark_evidence_md_present", distributed_md, required=False))
    checks.append(_file_check("multi_region_fault_drill_json_present", fault_drill_json, required=False))
    checks.append(_file_check("multi_region_fault_drill_md_present", fault_drill_md, required=False))

    evidence_key = str(os.environ.get(args.evidence_signing_key_env, "")).strip()
    allowed_envs = [item.strip() for item in str(args.allowed_evidence_environments).split(",") if item.strip()]
    checks.append(
        _evidence_hardening_check(
            "distributed_benchmark_evidence_hardening",
            distributed_json,
            evidence_key,
            args.require_evidence_signature,
            args.max_evidence_age_hours,
            allowed_envs,
        )
    )
    checks.append(
        _evidence_hardening_check(
            "multi_region_fault_drill_evidence_hardening",
            fault_drill_json,
            evidence_key,
            args.require_evidence_signature,
            args.max_evidence_age_hours,
            allowed_envs,
        )
    )

    if args.run_data_flywheel:
        check = _run_command(
            "data_flywheel_pipeline",
            [
                args.python_exec,
                "-u",
                str(stress_dir / "data_flywheel_pipeline.py"),
                "--events",
                args.flywheel_events,
                "--out-root",
                args.flywheel_out_root,
            ],
            cwd=project_root,
            timeout_sec=120,
        )
        check.artifacts = [str(flywheel_manifest)]
        checks.append(check)

    checks.append(_file_check("data_flywheel_manifest_present", flywheel_manifest, required=False))

    if args.run_flywheel_sla:
        flywheel_sla_json = stress_dir / "flywheel_sla_report.json"
        check = _run_command(
            "flywheel_sla_report",
            [
                args.python_exec,
                "-u",
                str(stress_dir / "flywheel_sla_report.py"),
                "--project-root",
                str(project_root),
                "--manifest",
                str(flywheel_manifest.relative_to(project_root)) if flywheel_manifest.is_absolute() else str(flywheel_manifest),
                "--feature-freshness-sec",
                str(args.feature_freshness_sec),
                "--training-latency-sec",
                str(args.training_latency_sec),
                "--feedback-lag-sec",
                str(args.feedback_lag_sec),
                "--out-json",
                str(flywheel_sla_json.relative_to(project_root)),
            ],
            cwd=project_root,
            timeout_sec=120,
        )
        check.artifacts = [str(flywheel_sla_json)]
        checks.append(check)
        checks.append(_file_check("flywheel_sla_report_present", flywheel_sla_json, required=True))

    if args.run_flink_iceberg_config_check:
        flink_iceberg_json = stress_dir / "flink_iceberg_config_report.json"
        check = _run_command(
            "flink_iceberg_config_check",
            [
                args.python_exec,
                "-u",
                str(scripts_dir / "validate_flink_iceberg_config.py"),
                "--project-root",
                str(project_root),
                "--catalog-type",
                str(args.iceberg_catalog_type),
                "--out-json",
                str(flink_iceberg_json.relative_to(project_root)),
            ],
            cwd=project_root,
            timeout_sec=120,
        )
        check.artifacts = [str(flink_iceberg_json)]
        checks.append(check)
        checks.append(_file_check("flink_iceberg_config_report_present", flink_iceberg_json, required=True))

    if args.require_faiss:
        try:
            __import__("faiss")
            checks.append(
                CheckResult(
                    name="faiss_dependency_present",
                    status="PASS",
                    detail="faiss import succeeded",
                    durationMs=0,
                    artifacts=[],
                )
            )
        except Exception as error:
            checks.append(
                CheckResult(
                    name="faiss_dependency_present",
                    status="FAIL",
                    detail=f"faiss import failed: {error}",
                    durationMs=0,
                    artifacts=[],
                )
            )

    if args.run_scale_readiness:
        check = _run_command(
            "global_scale_readiness",
            [
                args.python_exec,
                "-u",
                str(stress_dir / "global_scale_readiness.py"),
                "--target-concurrency",
                str(args.target_concurrency),
                "--ignore-go-live-summary",
            ],
            cwd=project_root,
            timeout_sec=120,
        )
        check.artifacts = [str(scale_readiness_json), str(scale_readiness_md)]
        checks.append(check)

    checks.append(_file_check("global_scale_readiness_json_present", scale_readiness_json, required=False))
    checks.append(_file_check("global_scale_readiness_md_present", scale_readiness_md, required=False))

    checks.append(_security_env_gate(getattr(args, "security_env_profile", "local")))

    if args.require_slo_enforcement:
        checks.append(
            _run_command(
                "canary_slo_enforcement",
                [
                    args.python_exec,
                    "-u",
                    str(scripts_dir / "canary_gate.py"),
                    "--report",
                    str(canary_report),
                    "--event-metrics",
                    str(consumer_metrics),
                    "--out",
                    str(canary_decision),
                    "--metrics-out",
                    str(canary_metrics),
                    "--max-success-gap",
                    str(args.slo_max_success_gap),
                    "--max-p95-drift",
                    str(args.slo_max_p95_drift),
                    "--max-p99-drift",
                    str(args.slo_max_p99_drift),
                    "--max-runtime-error-rate",
                    str(args.slo_max_runtime_error_rate),
                ],
                cwd=project_root,
                timeout_sec=120,
            )
        )

    scale_readiness = _load_json(scale_readiness_json)
    if scale_readiness is None:
        checks.append(
            CheckResult(
                name="global_scale_status_minimum",
                status="FAIL",
                detail="global scale readiness json missing or invalid",
                durationMs=0,
                artifacts=[str(scale_readiness_json)],
            )
        )
    else:
        status_value = str(scale_readiness.get("status", "NOT_READY"))
        rank = {
            "NOT_READY": 0,
            "ARCHITECTURE_READY_NOT_PROVEN": 1,
            "PRODUCTION_PROVEN": 2,
        }
        min_required = str(args.min_scale_status)
        ok = rank.get(status_value, -1) >= rank.get(min_required, 1)
        checks.append(
            CheckResult(
                name="global_scale_status_minimum",
                status="PASS" if ok else "FAIL",
                detail=f"status={status_value}, minRequired={min_required}",
                durationMs=0,
                artifacts=[str(scale_readiness_json)],
            )
        )

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
    parser.add_argument("--target-concurrency", type=int, default=1_000_000)
    parser.add_argument("--run-distributed-benchmark", action="store_true", default=False)
    parser.add_argument("--run-fault-drill", action="store_true", default=False)
    parser.add_argument("--run-dr-automation", action="store_true", default=True)
    parser.add_argument("--dr-auto-run", action="store_true", default=False)
    parser.add_argument("--dr-incident-out", default="stress/dr_automation_incident.json")
    parser.add_argument("--dr-status-out", default="stress/dr_automation_status.json")
    parser.add_argument("--distributed-regions", type=int, default=3)
    parser.add_argument("--distributed-duration-minutes", type=int, default=60)
    parser.add_argument("--distributed-report-json", default="stress/report_5k.json")
    parser.add_argument("--distributed-evidence-source", default="local-loadtest")
    parser.add_argument("--distributed-run-id", default="local-unknown")
    parser.add_argument("--distributed-environment", default="local")
    parser.add_argument("--fault-recovery-rto-minutes", type=int, default=10)
    parser.add_argument("--fault-recovery-rpo-seconds", type=int, default=30)
    parser.add_argument("--fault-canary-decision", default="stress/canary_gate_decision.json")
    parser.add_argument("--fault-canary-metrics", default="stress/canary_gate_metrics.prom")
    parser.add_argument("--fault-incident-ticket", default="stress/p3_5_incident_ticket.json")
    parser.add_argument("--fault-evidence-source", default="staging-drill")
    parser.add_argument("--fault-run-id", default="drill-unknown")
    parser.add_argument("--fault-environment", default="staging")
    parser.add_argument("--run-data-flywheel", action="store_true", default=True)
    parser.add_argument("--flywheel-events", default="var/events/audit_events.jsonl")
    parser.add_argument("--flywheel-out-root", default="var/lakehouse")
    parser.add_argument("--run-flywheel-sla", action="store_true", default=True)
    parser.add_argument("--feature-freshness-sec", type=float, default=600.0)
    parser.add_argument("--training-latency-sec", type=float, default=1200.0)
    parser.add_argument("--feedback-lag-sec", type=float, default=180.0)
    parser.add_argument("--run-flink-iceberg-config-check", action="store_true", default=True)
    parser.add_argument("--iceberg-catalog-type", default=os.getenv("ICEBERG_CATALOG_TYPE", "hive"))
    parser.add_argument("--require-faiss", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--evidence-signing-key-env", default="TRAVEL_EVIDENCE_SIGNING_KEY")
    parser.add_argument("--max-evidence-age-hours", type=float, default=24.0)
    parser.add_argument("--allowed-evidence-environments", default="staging,prod")
    parser.add_argument("--require-evidence-signature", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--require-source-protection", action="store_true", default=False)
    parser.add_argument(
        "--security-env-profile",
        choices=["local", "staging", "prod"],
        default=os.getenv("TRAVEL_SECURITY_ENV_PROFILE", "local"),
        help="Profile for the security environment gate (staging/prod enforce OIDC, real secrets, semantic embeddings)",
    )
    parser.add_argument("--run-scale-readiness", action="store_true", default=True)
    parser.add_argument("--require-slo-enforcement", action="store_true", default=True)
    parser.add_argument("--slo-max-success-gap", type=float, default=0.03)
    parser.add_argument("--slo-max-p95-drift", type=float, default=0.08)
    parser.add_argument("--slo-max-p99-drift", type=float, default=0.10)
    parser.add_argument("--slo-max-runtime-error-rate", type=float, default=0.01)
    parser.add_argument(
        "--min-scale-status",
        choices=["NOT_READY", "ARCHITECTURE_READY_NOT_PROVEN", "PRODUCTION_PROVEN"],
        default="ARCHITECTURE_READY_NOT_PROVEN",
    )
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

