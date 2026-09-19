"""Cross-implementation policy consistency check (single-source governance).

Verifies that every policy implementation declares the SAME limits and tier
definitions as the canonical contract ``data-contracts/policy-core/policy-core.v1.json``:

- Python runtime: ``travel_agent/access/control.py`` (evaluated via golden cases
  in tests/test_policy_core_parity.py)
- Go policy:      ``services/techgroup-enterprise-travel-policy-go/policy_core.go``
                  and ``policy.rego``
- Java gateway:   ``PolicyCoreSpec`` loads the contract JSON at runtime
                  (TRAVEL_POLICY_CORE_FILE); builtin defaults must still match.

Exit code 0 = all implementations aligned; 1 = drift detected (CI gate).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "data-contracts" / "policy-core" / "policy-core.v1.json"


def _fail(message: str, problems: list) -> None:
    problems.append(message)


def check_rego(problems: list) -> None:
    rego = (ROOT / "services" / "techgroup-enterprise-travel-policy-go" / "policy.rego").read_text(encoding="utf-8")
    pairs = [
        ("maxAgentSteps", "maxAgentSteps"),
        ("maxToolCalls", "maxToolCalls"),
    ]
    for input_key, json_key in pairs:
        matches = set(re.findall(rf"input\.{input_key}\s*<=\s*(\d+)", rego))
        if not matches:
            _fail(f"policy.rego: no upper-bound rule found for {input_key}", problems)
            continue
        for value in matches:
            if int(value) != CONTRACT_DATA["limits"][json_key]:
                _fail(
                    f"policy.rego: {input_key} <= {value} but contract says {CONTRACT_DATA['limits'][json_key]}",
                    problems,
                )


def check_go_defaults(problems: list) -> None:
    go = (ROOT / "services" / "techgroup-enterprise-travel-policy-go" / "policy_core.go").read_text(encoding="utf-8")
    for json_key, pattern in (
        ("maxAgentSteps", r'"maxAgentSteps":\s*(\d+)'),
        ("maxToolCalls", r'"maxToolCalls":\s*(\d+)'),
    ):
        matches = set(re.findall(pattern, go))
        for value in matches:
            if int(value) != CONTRACT_DATA["limits"][json_key]:
                _fail(
                    f"policy_core.go: {json_key} default {value} but contract says {CONTRACT_DATA['limits'][json_key]}",
                    problems,
                )


def check_java_runtime_consumes_contract(problems: list) -> None:
    spec = (ROOT / "services" / "techgroup-enterprise-travel-gateway" / "src" / "main" / "java" / "com" / "techgroup" / "travel" / "gateway" / "service" / "PolicyCoreSpec.java").read_text(encoding="utf-8")
    if "TRAVEL_POLICY_CORE_FILE" not in spec:
        _fail("PolicyCoreSpec: does not consume the policy-core contract file at runtime", problems)


def check_contract_tiers_shape(problems: list) -> None:
    for tier in ("basic", "silver", "gold", "platinum"):
        entry = CONTRACT_DATA["tiers"].get(tier)
        if not entry or not entry.get("tools") or not entry.get("engines"):
            _fail(f"contract: tier '{tier}' missing tools/engines", problems)


CONTRACT_DATA = json.loads(CONTRACT.read_text(encoding="utf-8"))


def main() -> int:
    problems: list = []
    check_contract_tiers_shape(problems)
    check_rego(problems)
    check_go_defaults(problems)
    check_java_runtime_consumes_contract(problems)

    report = {
        "check": "policy-consistency",
        "contract": "data-contracts/policy-core/policy-core.v1.json",
        "aligned": not problems,
        "problems": problems,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
