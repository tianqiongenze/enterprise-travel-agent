package main

import (
	"testing"
)

// TestEvaluateAllowAndDenyPaths drives the real rego policy through allow and
// deny paths, including the contract limits (maxAgentSteps<=50, maxToolCalls<=30).
func TestEvaluateAllowAndDenyPaths(t *testing.T) {
	if err := initPolicy(); err != nil {
		t.Fatalf("initPolicy failed: %v", err)
	}
	initDecisionLogWorkers()

	allowReq := PolicyRequest{
		TenantID:            "tenant-1",
		UserID:              "user-1",
		IdempotencyKey:      "idem-eval-1",
		PolicyID:            "policy-default",
		ConversationID:      "conv-1",
		City:                "北京",
		Days:                3,
		Budget:              3000,
		Travelers:           2,
		MembershipTier:      "basic",
		OrchestrationEngine: "langgraph",
		Preferences:         []string{"budget"},
		MaxAgentSteps:       10,
		MaxToolCalls:        10,
		AllowedTools:        []string{"search_hotels", "search_transports", "search_attractions"},
	}
	decision, reason, _ := evaluate(allowReq)
	if decision != "allow" || reason != "ok" {
		t.Fatalf("expected allow/ok, got %s/%s", decision, reason)
	}

	denySteps := allowReq
	denySteps.IdempotencyKey = "idem-eval-steps-deny"
	denySteps.MaxAgentSteps = 60
	decision, reason, _ = evaluate(denySteps)
	if decision != "deny" || reason != "maxAgentSteps exceeds policy limit" {
		t.Fatalf("expected deny for oversized steps, got %s/%s", decision, reason)
	}

	denyTools := allowReq
	denyTools.IdempotencyKey = "idem-eval-tools-deny"
	denyTools.AllowedTools = []string{"search_souvenirs"} // not in basic tier
	decision, reason, _ = evaluate(denyTools)
	if decision != "deny" {
		t.Fatalf("expected deny for tier tool violation, got %s/%s", decision, reason)
	}
}

// TestEvaluateDeniesEngineTierMismatch checks the tier/engine matrix.
func TestEvaluateDeniesEngineTierMismatch(t *testing.T) {
	if err := initPolicy(); err != nil {
		t.Fatalf("initPolicy failed: %v", err)
	}
	req := PolicyRequest{
		TenantID:            "tenant-1",
		UserID:              "user-engine-1",
		IdempotencyKey:      "idem-engine-1",
		PolicyID:            "policy-default",
		MembershipTier:      "basic",
		OrchestrationEngine: "oneagents", // oneagents requires gold/platinum
		MaxAgentSteps:       10,
		MaxToolCalls:        10,
		AllowedTools:        []string{"search_hotels", "search_transports", "search_attractions"},
	}
	decision, reason, _ := evaluate(req)
	if decision != "deny" || reason != "membershipTier cannot use current orchestration engine" {
		t.Fatalf("expected engine-tier deny, got %s/%s", decision, reason)
	}
}
