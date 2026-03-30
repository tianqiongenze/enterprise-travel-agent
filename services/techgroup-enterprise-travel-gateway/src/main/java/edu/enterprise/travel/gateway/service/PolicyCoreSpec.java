package edu.enterprise.travel.gateway.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;

/**
 * Immutable policy spec used by gateway policy guard.
 */
public final class PolicyCoreSpec {

    private final int maxAgentSteps;
    private final int maxToolCalls;
    private final Map<String, Set<String>> tierTools;
    private final Map<String, Set<String>> tierEngines;
    private final Map<String, String> engineAliases;

    private PolicyCoreSpec(
            int maxAgentSteps,
            int maxToolCalls,
            Map<String, Set<String>> tierTools,
            Map<String, Set<String>> tierEngines,
            Map<String, String> engineAliases
    ) {
        this.maxAgentSteps = maxAgentSteps;
        this.maxToolCalls = maxToolCalls;
        this.tierTools = tierTools;
        this.tierEngines = tierEngines;
        this.engineAliases = engineAliases;
    }

    /**
     * Loads policy spec from JSON file and falls back to built-in defaults when unavailable.
     */
    public static PolicyCoreSpec load() {
        String path = System.getenv().getOrDefault("TRAVEL_POLICY_CORE_FILE", "policy-core/policy-core.v1.json");
        try {
            ObjectMapper mapper = new ObjectMapper();
            JsonNode root = mapper.readTree(Files.readString(Path.of(path)));
            int maxSteps = root.path("limits").path("maxAgentSteps").asInt(50);
            int maxCalls = root.path("limits").path("maxToolCalls").asInt(30);

            Map<String, Set<String>> tools = new HashMap<>();
            Map<String, Set<String>> engines = new HashMap<>();
            JsonNode tiers = root.path("tiers");
            tiers.fieldNames().forEachRemaining(name -> {
                JsonNode tier = tiers.path(name);
                Set<String> tierTools = new HashSet<>();
                tier.path("tools").forEach(item -> tierTools.add(item.asText()));
                Set<String> tierEngines = new HashSet<>();
                tier.path("engines").forEach(item -> tierEngines.add(item.asText()));
                tools.put(name, tierTools);
                engines.put(name, tierEngines);
            });

            Map<String, String> aliases = new HashMap<>();
            JsonNode aliasesNode = root.path("engineAliases");
            aliasesNode.fieldNames().forEachRemaining(name -> aliases.put(name, aliasesNode.path(name).asText()));

            if (!tools.isEmpty() && !engines.isEmpty()) {
                return new PolicyCoreSpec(maxSteps, maxCalls, tools, engines, aliases);
            }
        } catch (Exception ignored) {
        }
        return defaults();
    }

    public static PolicyCoreSpec defaults() {
        Map<String, Set<String>> tools = new HashMap<>();
        tools.put("basic", Set.of("search_hotels", "search_transports", "search_attractions"));
        tools.put("silver", Set.of("search_hotels", "search_transports", "search_attractions", "search_foods"));
        tools.put("gold", Set.of("search_hotels", "search_transports", "search_attractions", "search_foods", "search_events"));
        tools.put("platinum", Set.of("search_hotels", "search_transports", "search_attractions", "search_foods", "search_events"));

        Map<String, Set<String>> engines = new HashMap<>();
        engines.put("basic", Set.of("langgraph"));
        engines.put("silver", Set.of("langgraph", "agentscope"));
        engines.put("gold", Set.of("langgraph", "agentscope", "oneagents"));
        engines.put("platinum", Set.of("langgraph", "agentscope", "oneagents"));

        Map<String, String> aliases = new HashMap<>();
        aliases.put("agentscope-ai", "agentscope");
        aliases.put("oneagent", "oneagents");
        aliases.put("native", "local");

        return new PolicyCoreSpec(50, 30, tools, engines, aliases);
    }

    public int maxAgentSteps() {
        return maxAgentSteps;
    }

    public int maxToolCalls() {
        return maxToolCalls;
    }

    public Set<String> toolsForTier(String tier) {
        return tierTools.getOrDefault(tier, tierTools.getOrDefault("basic", Collections.emptySet()));
    }

    public boolean hasTier(String tier) {
        return tierTools.containsKey(tier);
    }

    public Set<String> enginesForTier(String tier) {
        return tierEngines.getOrDefault(tier, tierEngines.getOrDefault("basic", Collections.emptySet()));
    }

    public String normalizeEngine(String engine) {
        String normalized = engine == null ? "" : engine.trim().toLowerCase();
        return engineAliases.getOrDefault(normalized, normalized);
    }
}
