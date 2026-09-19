package authz

# Policy rules matching data-contracts/policy-core/policy-core.v1.json.
# Verified by scripts/check_policy_consistency.py and main_test.go.

default allow = false
default reason = "policy denied"

max_agent_steps = 50
max_tool_calls = 30

tier_tools = {
  "basic": {"search_hotels", "search_transports", "search_attractions"},
  "silver": {"search_hotels", "search_transports", "search_attractions", "search_foods", "search_activities"},
  "gold": {"search_hotels", "search_transports", "search_attractions", "search_foods", "search_events", "search_activities", "search_souvenirs"},
  "platinum": {"search_hotels", "search_transports", "search_attractions", "search_foods", "search_events", "search_activities", "search_souvenirs"},
}

tier_engines = {
  "basic": {"langgraph"},
  "silver": {"langgraph", "agentscope"},
  "gold": {"langgraph", "agentscope", "oneagents"},
  "platinum": {"langgraph", "agentscope", "oneagents"},
}

engine_aliases = {
  "agentscope-ai": "agentscope",
  "oneagent": "oneagents",
  "native": "local",
}

valid_tier {
  tier_tools[lower(input.membershipTier)]
}

normalized_tier = t {
  valid_tier
  t := lower(input.membershipTier)
}

normalized_tier = "basic" {
  not valid_tier
}

normalized_engine = e {
  raw := lower(input.orchestrationEngine)
  e := object.get(engine_aliases, raw, raw)
}

allow {
  input.maxAgentSteps <= 50
  input.maxToolCalls <= 30
  tools_within_tier
  engine_valid_for_tier
}

reason = "ok" {
  allow
}

reason = "maxAgentSteps exceeds policy limit" {
  input.maxAgentSteps > 50
}

reason = "maxToolCalls exceeds policy limit" {
  input.maxToolCalls > 30
}

reason = "allowedTools contains unsupported tool" {
  not tools_within_tier
}

reason = "membershipTier cannot use current orchestration engine" {
  not engine_valid_for_tier
}

# Every requested tool must be present in the tier's tool set.
tools_within_tier {
  requested := {t | t := input.allowedTools[_]}
  allowed := tier_tools[normalized_tier]
  count(requested - allowed) == 0
}

engine_valid_for_tier {
  tier_engines[normalized_tier][normalized_engine]
}
