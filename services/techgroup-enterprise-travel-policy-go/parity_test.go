// Package main provides golden-parity tests between the Go policy service
// and data-contracts/policy-core/cases/golden_cases.v1.json (the same file
// tests/test_policy_core_parity.py runs against the Python evaluator).
package main

import (
	"encoding/json"
	"os"
	"testing"
)

type goldenCase struct {
	Name     string `json:"name"`
	Input    struct {
		Tier          string   `json:"tier"`
		Engine        string   `json:"engine"`
		AllowedTools  []string `json:"allowedTools"`
		MaxAgentSteps int      `json:"maxAgentSteps"`
		MaxToolCalls  int      `json:"maxToolCalls"`
	} `json:"input"`
	Expected struct {
		Allow  bool   `json:"allow"`
		Reason string `json:"reason"`
	} `json:"expected"`
}

func TestGoldenCasesParity(t *testing.T) {
	if err := initPolicy(); err != nil {
		t.Fatalf("initPolicy: %v", err)
	}
	initDecisionLogWorkers()

	raw, err := os.ReadFile("../../data-contracts/policy-core/cases/golden_cases.v1.json")
	if err != nil {
		t.Fatalf("read golden cases: %v", err)
	}
	var cases []goldenCase
	if err := json.Unmarshal(raw, &cases); err != nil {
		t.Fatalf("parse golden cases: %v", err)
	}
	if len(cases) == 0 {
		t.Fatal("golden cases file is empty")
	}

	for _, tc := range cases {
		tc := tc
		t.Run(tc.Name, func(t *testing.T) {
			req := PolicyRequest{
				// Unique cache keys so cases never share a cached decision.
				TenantID:            "parity",
				UserID:              tc.Name,
				MembershipTier:      tc.Input.Tier,
				OrchestrationEngine: tc.Input.Engine,
				AllowedTools:        tc.Input.AllowedTools,
				MaxAgentSteps:       tc.Input.MaxAgentSteps,
				MaxToolCalls:        tc.Input.MaxToolCalls,
			}
			decision, reason, _ := evaluate(req)
			wantDecision := "deny"
			if tc.Expected.Allow {
				wantDecision = "allow"
			}
			if decision != wantDecision {
				t.Fatalf("decision = %q, want %q", decision, wantDecision)
			}
			if reason != tc.Expected.Reason {
				t.Fatalf("reason = %q, want %q", reason, tc.Expected.Reason)
			}
		})
	}
}

func TestEngineAliasNormalization(t *testing.T) {
	cases := map[string]string{
		"agentscope-ai": "agentscope",
		"oneagent":      "oneagents",
		"native":        "local",
		"langgraph":     "langgraph",
		"":              "",
	}
	for raw, want := range cases {
		if got := policyCoreNormalizeEngine(raw); got != want {
			t.Fatalf("normalize(%q) = %q, want %q", raw, got, want)
		}
	}
}
