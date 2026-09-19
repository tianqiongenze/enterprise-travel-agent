// Package main provides the service entrypoint.
package main

import (
	"os"

	json "github.com/goccy/go-json"
)

type policyCoreTier struct {
	Tools   []string `json:"tools"`
	Engines []string `json:"engines"`
}

type policyCoreSpec struct {
	Version       string                    `json:"version"`
	Limits        map[string]int            `json:"limits"`
	Tiers         map[string]policyCoreTier `json:"tiers"`
	EngineAliases map[string]string         `json:"engineAliases"`
}

var activePolicyCore = loadPolicyCoreSpec()

func loadPolicyCoreSpec() policyCoreSpec {
	path := os.Getenv("TRAVEL_POLICY_CORE_FILE")
	if path == "" {
		path = "../policy-core/policy-core.v1.json"
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return defaultPolicyCoreSpec()
	}
	var spec policyCoreSpec
	if unmarshalErr := json.Unmarshal(data, &spec); unmarshalErr != nil {
		return defaultPolicyCoreSpec()
	}
	if len(spec.Tiers) == 0 {
		return defaultPolicyCoreSpec()
	}
	return spec
}

func defaultPolicyCoreSpec() policyCoreSpec {
	return policyCoreSpec{
		Version: "policy-core.v1",
		Limits:  map[string]int{"maxAgentSteps": 50, "maxToolCalls": 30},
		Tiers: map[string]policyCoreTier{
			"basic":    {Tools: []string{"search_hotels", "search_transports", "search_attractions"}, Engines: []string{"langgraph"}},
			"silver":   {Tools: []string{"search_hotels", "search_transports", "search_attractions", "search_foods"}, Engines: []string{"langgraph", "agentscope"}},
			"gold":     {Tools: []string{"search_hotels", "search_transports", "search_attractions", "search_foods", "search_events"}, Engines: []string{"langgraph", "agentscope", "oneagents"}},
			"platinum": {Tools: []string{"search_hotels", "search_transports", "search_attractions", "search_foods", "search_events"}, Engines: []string{"langgraph", "agentscope", "oneagents"}},
		},
		EngineAliases: map[string]string{"agentscope-ai": "agentscope", "oneagent": "oneagents", "native": "local"},
	}
}

func policyCoreNormalizeEngine(engine string) string {
	if alias, ok := activePolicyCore.EngineAliases[engine]; ok {
		return alias
	}
	return engine
}
