package authz

default allow = false
default reason = "policy denied"

allow {
  input.maxAgentSteps <= 50
  input.maxToolCalls <= 30
  valid_tools
  valid_engine
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
  not valid_tools
}

reason = "membershipTier cannot use current orchestration engine" {
  not valid_engine
}

valid_tools {
  tier := normalized_tier
  every t in input.allowedTools {
    tool_allowed_for_tier(tier, t)
  }
}

valid_engine {
  engine_allowed_for_tier(normalized_tier, input.orchestrationEngine)
}

normalized_tier := tier {
  lower(input.membershipTier) == "silver"
  tier := "silver"
}

normalized_tier := tier {
  lower(input.membershipTier) == "gold"
  tier := "gold"
}

normalized_tier := tier {
  lower(input.membershipTier) == "platinum"
  tier := "platinum"
}

normalized_tier := "basic" {
  not lower(input.membershipTier) == "silver"
  not lower(input.membershipTier) == "gold"
  not lower(input.membershipTier) == "platinum"
}

tool_allowed_for_tier("basic", t) {
  t == "search_hotels" or t == "search_transports" or t == "search_attractions"
}

tool_allowed_for_tier("silver", t) {
  tool_allowed_for_tier("basic", t)
} {
  t == "search_foods"
}

tool_allowed_for_tier("gold", t) {
  tool_allowed_for_tier("silver", t)
} {
  t == "search_events"
}

tool_allowed_for_tier("platinum", t) {
  tool_allowed_for_tier("gold", t)
}

normalized_engine := "agentscope" {
  lower(input.orchestrationEngine) == "agentscope-ai"
}

normalized_engine := "oneagents" {
  lower(input.orchestrationEngine) == "oneagent"
}

normalized_engine := lower(input.orchestrationEngine) {
  not lower(input.orchestrationEngine) == "agentscope-ai"
  not lower(input.orchestrationEngine) == "oneagent"
}

engine_allowed_for_tier("basic", e) {
  normalized := normalized_engine
  e == normalized
  e == "langgraph"
}

engine_allowed_for_tier("silver", e) {
  normalized := normalized_engine
  e == normalized
  e == "langgraph" or e == "agentscope"
}

engine_allowed_for_tier("gold", e) {
  normalized := normalized_engine
  e == normalized
  e == "langgraph" or e == "agentscope" or e == "oneagents"
}

engine_allowed_for_tier("platinum", e) {
  engine_allowed_for_tier("gold", e)
}
