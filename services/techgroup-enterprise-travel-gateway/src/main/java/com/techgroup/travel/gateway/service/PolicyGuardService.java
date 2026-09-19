package com.techgroup.travel.gateway.service;

import com.techgroup.travel.gateway.api.dto.TravelRecommendRequest;
import io.lettuce.core.RedisClient;
import io.lettuce.core.RedisURI;
import io.lettuce.core.api.StatefulRedisConnection;
import io.lettuce.core.api.async.RedisAsyncCommands;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Gateway-side policy guard.
 *
 * <p>Responsibilities:
 * <ul>
 *     <li>enforce local policy constraints before runtime calls,</li>
 *     <li>optionally call external Go policy runtime,</li>
 *     <li>cache policy decisions in memory and optional Redis.</li>
 * </ul>
 */
@Service
public class PolicyGuardService {

    private static final long DEFAULT_CACHE_TTL_MS = 3000L;

    private final RestTemplate restTemplate;
    private final ConcurrentHashMap<String, CachedDecision> cache = new ConcurrentHashMap<>();
    private final AtomicLong cacheHits = new AtomicLong(0);
    private final AtomicLong cacheMisses = new AtomicLong(0);
    private final String redisKeyPrefix;
    private final PolicyCoreSpec policyCoreSpec;
    private final RedisClient redisClient;
    private final StatefulRedisConnection<String, String> redisConnection;
    private final RedisAsyncCommands<String, String> redisAsync;
    private final ConfigProvider configProvider;
    private final GoPolicyEvaluator goPolicyEvaluator;

    public PolicyGuardService() {
        this.configProvider = new EnvConfigProvider();
        this.restTemplate = createRestTemplate(configProvider);
        this.policyCoreSpec = PolicyCoreSpec.load();
        this.redisKeyPrefix = getConfig("TRAVEL_POLICY_CACHE_REDIS_PREFIX", "policy:decision");

        RedisClient client = null;
        StatefulRedisConnection<String, String> connection = null;
        RedisAsyncCommands<String, String> async = null;
        if (isTrue("TRAVEL_POLICY_CACHE_REDIS_ENABLED", false)) {
            try {
                String redisUrl = getConfig("TRAVEL_POLICY_CACHE_REDIS_URL", "redis://127.0.0.1:7000");
                client = RedisClient.create(RedisURI.create(redisUrl));
                connection = client.connect();
                async = connection.async();
            } catch (Exception error) {
                client = null;
                connection = null;
                async = null;
                System.out.println("[policy-guard] redis cache unavailable: " + error.getMessage());
            }
        }
        this.redisClient = client;
        this.redisConnection = connection;
        this.redisAsync = async;
        this.goPolicyEvaluator = this::evaluateWithGo;
    }

    /**
     * Testing constructor for deterministic unit tests.
     */
    PolicyGuardService(
            RestTemplate restTemplate,
            PolicyCoreSpec policyCoreSpec,
            RedisAsyncCommands<String, String> redisAsync,
            String redisKeyPrefix,
            ConfigProvider configProvider,
            GoPolicyEvaluator goPolicyEvaluator
    ) {
        this.restTemplate = restTemplate;
        this.policyCoreSpec = policyCoreSpec;
        this.redisAsync = redisAsync;
        this.redisKeyPrefix = redisKeyPrefix;
        this.configProvider = configProvider;
        this.goPolicyEvaluator = goPolicyEvaluator;
        this.redisClient = null;
        this.redisConnection = null;
    }

    /**
     * Validates whether a recommendation request can pass gateway policy checks.
     */
    public void validate(TravelRecommendRequest request) {
        String backend = getConfig("TRAVEL_POLICY_BACKEND", "java").trim().toLowerCase();
        if ("go".equals(backend) || ("canary".equals(backend) && shouldUseGo(request))) {
            String cacheKey = buildCacheKey(request);
            PolicyDecision decision = getCachedDecision(cacheKey);
            if (decision == null) {
                cacheMisses.incrementAndGet();
                decision = goPolicyEvaluator.evaluate(request);
                cacheDecision(cacheKey, decision);
            } else {
                cacheHits.incrementAndGet();
            }
            if (!"allow".equalsIgnoreCase(decision.decision)) {
                throw new IllegalArgumentException(decision.reason);
            }
            if (isTrue("TRAVEL_POLICY_SHADOW", false)) {
                PolicyDecision javaDecision = evaluateLocal(request);
                if (!javaDecision.decision.equalsIgnoreCase(decision.decision)) {
                    System.out.println("policy_shadow_diff java=" + javaDecision.decision + " go=" + decision.decision + " reason=" + decision.reason);
                }
            }
            return;
        }

        PolicyDecision local = evaluateLocal(request);
        if (!"allow".equalsIgnoreCase(local.decision)) {
            throw new IllegalArgumentException(local.reason);
        }
    }

    private boolean shouldUseGo(TravelRecommendRequest request) {
        int percent = parseInt("TRAVEL_POLICY_CANARY_PERCENT", 0);
        percent = Math.max(0, Math.min(100, percent));
        if (percent == 0) {
            return false;
        }
        if (percent == 100) {
            return true;
        }
        String input = request.tenantId() + ":" + request.userId() + ":" + request.idempotencyKey();
        int bucket = hashToBucket(input);
        return bucket < percent;
    }

    private int hashToBucket(String input) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] bytes = digest.digest(input.getBytes(StandardCharsets.UTF_8));
            int value = ((bytes[0] & 0xff) << 24) | ((bytes[1] & 0xff) << 16) | ((bytes[2] & 0xff) << 8) | (bytes[3] & 0xff);
            if (value < 0) {
                value = -value;
            }
            return value % 100;
        } catch (Exception error) {
            return 0;
        }
    }

    private PolicyDecision evaluateLocal(TravelRecommendRequest request) {
        if (request.maxAgentSteps() > policyCoreSpec.maxAgentSteps()) {
            return new PolicyDecision("deny", "maxAgentSteps exceeds policy limit");
        }
        if (request.maxToolCalls() > policyCoreSpec.maxToolCalls()) {
            return new PolicyDecision("deny", "maxToolCalls exceeds policy limit");
        }

        String tier = normalizeTier(request.membershipTier());
        Set<String> tierTools = policyCoreSpec.toolsForTier(tier);
        Set<String> allowed = new HashSet<>(request.allowedTools());
        if (!tierTools.containsAll(allowed)) {
            return new PolicyDecision("deny", "allowedTools contains unsupported tool");
        }

        String engine = normalizeEngine(getConfig("TRAVEL_ORCHESTRATION_ENGINE", "langgraph"));
        Set<String> tierEngines = policyCoreSpec.enginesForTier(tier);
        if (!tierEngines.contains(engine)) {
            return new PolicyDecision("deny", "membershipTier cannot use current orchestration engine");
        }
        return new PolicyDecision("allow", "ok");
    }

    private PolicyDecision evaluateWithGo(TravelRecommendRequest request) {
        String baseUrl = getConfig("TRAVEL_GO_POLICY_URL", "http://go-policy:8091");
        Map<String, Object> payload = new HashMap<>();
        payload.put("tenantId", request.tenantId());
        payload.put("userId", request.userId());
        payload.put("policyId", request.policyId());
        payload.put("conversationId", request.conversationId());
        payload.put("idempotencyKey", request.idempotencyKey());
        payload.put("city", request.city());
        payload.put("days", request.days());
        payload.put("budget", request.budget());
        payload.put("travelers", request.travelers());
        payload.put("membershipTier", normalizeTier(request.membershipTier()));
        payload.put("orchestrationEngine", normalizeEngine(getConfig("TRAVEL_ORCHESTRATION_ENGINE", "langgraph")));
        payload.put("preferences", request.preferences());
        payload.put("maxAgentSteps", request.maxAgentSteps());
        payload.put("maxToolCalls", request.maxToolCalls());
        payload.put("allowedTools", request.allowedTools());

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        ResponseEntity<Map<String, Object>> response = restTemplate.exchange(
                baseUrl + "/v1/policy/evaluate",
                HttpMethod.POST,
                new HttpEntity<>(payload, headers),
                new ParameterizedTypeReference<>() {
                }
        );
        Map<String, Object> body = response.getBody();
        if (body == null) {
            return new PolicyDecision("deny", "policy response empty");
        }
        Object decision = body.get("decision");
        Object reason = body.get("reason");
        return new PolicyDecision(
                decision == null ? "deny" : decision.toString(),
                reason == null ? "policy denied" : reason.toString()
        );
    }

    private String buildCacheKey(TravelRecommendRequest request) {
        return request.tenantId()
                + "|" + request.userId()
                + "|" + request.idempotencyKey()
                + "|" + request.maxAgentSteps()
                + "|" + request.maxToolCalls()
                + "|" + normalizeTier(request.membershipTier())
                + "|" + normalizeEngine(getConfig("TRAVEL_ORCHESTRATION_ENGINE", "langgraph"));
    }

    private String normalizeTier(String tier) {
        if (tier == null || tier.isBlank()) {
            return "basic";
        }
        String normalized = tier.trim().toLowerCase();
        if (policyCoreSpec.hasTier(normalized)) {
            return normalized;
        }
        return "basic";
    }

    private String normalizeEngine(String engine) {
        if (engine == null || engine.isBlank()) {
            return "langgraph";
        }
        return policyCoreSpec.normalizeEngine(engine);
    }

    private PolicyDecision getCachedDecision(String cacheKey) {
        CachedDecision cached = cache.get(cacheKey);
        if (cached == null) {
            return getRedisCachedDecision(cacheKey);
        }
        if (System.currentTimeMillis() > cached.expireAtMs) {
            cache.remove(cacheKey);
            return getRedisCachedDecision(cacheKey);
        }
        return cached.decision;
    }

    private void cacheDecision(String cacheKey, PolicyDecision decision) {
        long ttlMs = Math.max(500L, parseLong("TRAVEL_POLICY_CACHE_TTL_MS", DEFAULT_CACHE_TTL_MS));
        cache.put(cacheKey, new CachedDecision(decision, System.currentTimeMillis() + ttlMs));
        if (redisAsync != null) {
            try {
                String value = decision.decision + "|" + decision.reason;
                redisAsync.setex(redisKey(cacheKey), Math.max(1L, ttlMs / 1000L), value);
            } catch (Exception ignored) {
            }
        }
        if (cache.size() > 10000) {
            cache.clear();
        }
    }

    private PolicyDecision getRedisCachedDecision(String cacheKey) {
        if (redisAsync == null) {
            return null;
        }
        try {
            String row = redisAsync.get(redisKey(cacheKey)).get(120, TimeUnit.MILLISECONDS);
            if (row == null || row.isBlank()) {
                return null;
            }
            String[] parts = row.split("\\|", 2);
            String decision = parts.length > 0 ? parts[0] : "deny";
            String reason = parts.length > 1 ? parts[1] : "policy denied";
            return new PolicyDecision(decision, reason);
        } catch (Exception error) {
            return null;
        }
    }

    private String redisKey(String cacheKey) {
        return redisKeyPrefix + ":" + cacheKey;
    }

    /**
     * Exposes in-memory hit/miss counters for gateway observability APIs.
     */
    public Map<String, Object> cacheStats() {
        long hits = cacheHits.get();
        long misses = cacheMisses.get();
        long total = hits + misses;
        double hitRatio = total == 0 ? 0.0 : (double) hits / (double) total;
        return Map.of(
                "cacheSize", cache.size(),
                "cacheHits", hits,
                "cacheMisses", misses,
                "cacheHitRatio", hitRatio
        );
    }

    private RestTemplate createRestTemplate(ConfigProvider provider) {
        int connectTimeoutMs = Math.max(100, parseInt(provider, "TRAVEL_POLICY_HTTP_CONNECT_TIMEOUT_MS", 300));
        int readTimeoutMs = Math.max(200, parseInt(provider, "TRAVEL_POLICY_HTTP_READ_TIMEOUT_MS", 700));
        SimpleClientHttpRequestFactory requestFactory = new SimpleClientHttpRequestFactory();
        requestFactory.setConnectTimeout(connectTimeoutMs);
        requestFactory.setReadTimeout(readTimeoutMs);
        return new RestTemplate(requestFactory);
    }

    private boolean isTrue(String key, boolean defaultValue) {
        return Boolean.parseBoolean(getConfig(key, String.valueOf(defaultValue)));
    }

    private int parseInt(String key, int defaultValue) {
        return parseInt(configProvider, key, defaultValue);
    }

    private int parseInt(ConfigProvider provider, String key, int defaultValue) {
        try {
            return Integer.parseInt(provider.get(key, String.valueOf(defaultValue)));
        } catch (NumberFormatException error) {
            return defaultValue;
        }
    }

    private long parseLong(String key, long defaultValue) {
        try {
            return Long.parseLong(getConfig(key, String.valueOf(defaultValue)));
        } catch (NumberFormatException error) {
            return defaultValue;
        }
    }

    private String getConfig(String key, String defaultValue) {
        return configProvider.get(key, defaultValue);
    }

    @FunctionalInterface
    interface ConfigProvider {
        String get(String key, String defaultValue);
    }

    @FunctionalInterface
    interface GoPolicyEvaluator {
        PolicyDecision evaluate(TravelRecommendRequest request);
    }

    private static class EnvConfigProvider implements ConfigProvider {
        @Override
        public String get(String key, String defaultValue) {
            return System.getenv().getOrDefault(key, defaultValue);
        }
    }

    static class PolicyDecision {
        final String decision;
        final String reason;

        PolicyDecision(String decision, String reason) {
            this.decision = decision;
            this.reason = reason;
        }
    }

    private static class CachedDecision {
        final PolicyDecision decision;
        final long expireAtMs;

        CachedDecision(PolicyDecision decision, long expireAtMs) {
            this.decision = decision;
            this.expireAtMs = expireAtMs;
        }
    }
}
