"""Module provides service components and helpers."""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set


@dataclass(frozen=True)
class TierPolicy:
    name: str
    tools: Set[str]
    engines: Set[str]


_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_POLICY_CANDIDATES = [
    _ROOT / "policy-core" / "policy-core.v1.json",
    _ROOT / "data-contracts" / "policy-core" / "policy-core.v1.json",
]
_DEFAULT_LIMITS = {"maxAgentSteps": 50, "maxToolCalls": 30}
_DEFAULT_ALIASES = {"agentscope-ai": "agentscope", "oneagent": "oneagents", "native": "local"}
_DEFAULT_TIER_POLICIES: Dict[str, TierPolicy] = {
    "basic": TierPolicy("basic", {"search_hotels", "search_transports", "search_attractions"}, {"langgraph"}),
    "silver": TierPolicy("silver", {"search_hotels", "search_transports", "search_attractions", "search_foods"}, {"langgraph", "agentscope"}),
    "gold": TierPolicy("gold", {"search_hotels", "search_transports", "search_attractions", "search_foods", "search_events"}, {"langgraph", "agentscope", "oneagents"}),
    "platinum": TierPolicy("platinum", {"search_hotels", "search_transports", "search_attractions", "search_foods", "search_events"}, {"langgraph", "agentscope", "oneagents"}),
}


@dataclass(frozen=True)
class PolicyDecision:
    allow: bool
    reason: str


def _load_policy_core() -> tuple[Dict[str, TierPolicy], Dict[str, int], Dict[str, str]]:
    default_path = next((candidate for candidate in _DEFAULT_POLICY_CANDIDATES if candidate.exists()), _DEFAULT_POLICY_CANDIDATES[0])
    path = os.getenv("TRAVEL_POLICY_CORE_FILE", str(default_path))
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        tiers = raw.get("tiers", {}) if isinstance(raw, dict) else {}
        policies: Dict[str, TierPolicy] = {}
        for tier_name, payload in tiers.items():
            if not isinstance(payload, dict):
                continue
            tools = {str(item) for item in payload.get("tools", [])}
            engines = {str(item) for item in payload.get("engines", [])}
            policies[str(tier_name)] = TierPolicy(name=str(tier_name), tools=tools, engines=engines)
        if not policies:
            policies = dict(_DEFAULT_TIER_POLICIES)
        limits_raw = raw.get("limits", {}) if isinstance(raw, dict) else {}
        limits = {
            "maxAgentSteps": int(limits_raw.get("maxAgentSteps", _DEFAULT_LIMITS["maxAgentSteps"])),
            "maxToolCalls": int(limits_raw.get("maxToolCalls", _DEFAULT_LIMITS["maxToolCalls"])),
        }
        aliases_raw = raw.get("engineAliases", {}) if isinstance(raw, dict) else {}
        aliases = {str(key): str(value) for key, value in aliases_raw.items()} if isinstance(aliases_raw, dict) else dict(_DEFAULT_ALIASES)
        if not aliases:
            aliases = dict(_DEFAULT_ALIASES)
        return policies, limits, aliases
    except Exception:
        return dict(_DEFAULT_TIER_POLICIES), dict(_DEFAULT_LIMITS), dict(_DEFAULT_ALIASES)


_tier_policies, _limits, _aliases = _load_policy_core()


def get_tier_policy(tier: str) -> TierPolicy:
    return _tier_policies.get((tier or "").strip().lower(), _tier_policies["basic"])


def enforce_tools_for_tier(tier: str, requested_tools: List[str]) -> List[str]:
    policy = get_tier_policy(tier)
    allowed: List[str] = []
    for item in requested_tools:
        if item in policy.tools and item not in allowed:
            allowed.append(item)
    return allowed


def evaluate_policy(
    tier: str,
    engine: str,
    allowed_tools: List[str],
    max_agent_steps: int,
    max_tool_calls: int,
) -> PolicyDecision:
    if max_agent_steps > int(_limits["maxAgentSteps"]):
        return PolicyDecision(False, "maxAgentSteps exceeds policy limit")
    if max_tool_calls > int(_limits["maxToolCalls"]):
        return PolicyDecision(False, "maxToolCalls exceeds policy limit")
    policy = get_tier_policy(tier)
    if not set(allowed_tools).issubset(policy.tools):
        return PolicyDecision(False, "allowedTools contains unsupported tool")
    normalized_engine = _aliases.get(engine.strip().lower(), engine.strip().lower())
    if normalized_engine not in policy.engines:
        return PolicyDecision(False, "membershipTier cannot use current orchestration engine")
    return PolicyDecision(True, "ok")


