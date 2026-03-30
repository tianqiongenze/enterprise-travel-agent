package edu.enterprise.travel.gateway.service;

import edu.enterprise.travel.gateway.api.dto.TravelRecommendRequest;
import io.lettuce.core.RedisFuture;
import io.lettuce.core.api.async.RedisAsyncCommands;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;
import org.springframework.web.client.RestTemplate;

import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;

import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;

class PolicyGuardServiceTest {

    private final PolicyGuardService service = new PolicyGuardService();

    @Test
    void validateShouldPassForSupportedTools() {
        service.validate(sampleRequest(List.of("search_hotels", "search_transports", "search_attractions")));
    }

    @Test
    void validateShouldRejectUnsupportedTool() {
        Assertions.assertThrows(IllegalArgumentException.class,
                () -> service.validate(sampleRequest(List.of("unknown_tool"))));
    }

    @Test
    void cacheStatsShouldExposeCoreFields() {
        Map<String, Object> stats = service.cacheStats();
        Assertions.assertTrue(stats.containsKey("cacheSize"));
        Assertions.assertTrue(stats.containsKey("cacheHits"));
        Assertions.assertTrue(stats.containsKey("cacheMisses"));
        Assertions.assertTrue(stats.containsKey("cacheHitRatio"));
    }

    @Test
    void validateShouldUseGoBackendAndHitInMemoryCache() {
        @SuppressWarnings("unchecked")
        RedisAsyncCommands<String, String> redisAsync = Mockito.mock(RedisAsyncCommands.class);
        AtomicInteger goCalls = new AtomicInteger(0);

        PolicyGuardService goService = new PolicyGuardService(
                new RestTemplate(),
                PolicyCoreSpec.defaults(),
                redisAsync,
                "policy:test",
                fixedConfig(Map.of(
                        "TRAVEL_POLICY_BACKEND", "go",
                        "TRAVEL_ORCHESTRATION_ENGINE", "langgraph",
                        "TRAVEL_POLICY_CACHE_TTL_MS", "3000"
                )),
                request -> {
                    goCalls.incrementAndGet();
                    return new PolicyGuardService.PolicyDecision("allow", "ok-from-go");
                }
        );

        TravelRecommendRequest request = sampleRequest(List.of("search_hotels", "search_transports", "search_attractions"));
        goService.validate(request);
        goService.validate(request);

        Assertions.assertEquals(1, goCalls.get(), "Go backend should be called once due to cache hit on second request");
        Map<String, Object> stats = goService.cacheStats();
        Assertions.assertEquals(1L, stats.get("cacheHits"));
        Assertions.assertEquals(1L, stats.get("cacheMisses"));
        Mockito.verify(redisAsync).setex(anyString(), eq(3L), eq("allow|ok-from-go"));
    }

    @Test
    void validateShouldReadRedisDecisionBeforeCallingGo() throws Exception {
        @SuppressWarnings("unchecked")
        RedisAsyncCommands<String, String> redisAsync = Mockito.mock(RedisAsyncCommands.class);
        @SuppressWarnings("unchecked")
        RedisFuture<String> redisFuture = Mockito.mock(RedisFuture.class);
        Mockito.when(redisFuture.get(anyLong(), eq(java.util.concurrent.TimeUnit.MILLISECONDS))).thenReturn("allow|redis-hit");
        Mockito.when(redisAsync.get(anyString())).thenReturn(redisFuture);

        AtomicInteger goCalls = new AtomicInteger(0);
        PolicyGuardService goService = new PolicyGuardService(
                new RestTemplate(),
                PolicyCoreSpec.defaults(),
                redisAsync,
                "policy:test",
                fixedConfig(Map.of(
                        "TRAVEL_POLICY_BACKEND", "go",
                        "TRAVEL_ORCHESTRATION_ENGINE", "langgraph"
                )),
                request -> {
                    goCalls.incrementAndGet();
                    return new PolicyGuardService.PolicyDecision("allow", "ok");
                }
        );

        goService.validate(sampleRequest(List.of("search_hotels", "search_transports", "search_attractions")));

        Assertions.assertEquals(0, goCalls.get(), "Redis hit should bypass Go evaluation");
        Map<String, Object> stats = goService.cacheStats();
        Assertions.assertEquals(1L, stats.get("cacheHits"));
        Assertions.assertEquals(0L, stats.get("cacheMisses"));
        Mockito.verify(redisAsync).get(anyString());
    }

    @Test
    void validateShouldThrowWhenGoPolicyDenies() {
        PolicyGuardService goService = new PolicyGuardService(
                new RestTemplate(),
                PolicyCoreSpec.defaults(),
                null,
                "policy:test",
                fixedConfig(Map.of(
                        "TRAVEL_POLICY_BACKEND", "go",
                        "TRAVEL_ORCHESTRATION_ENGINE", "langgraph"
                )),
                request -> new PolicyGuardService.PolicyDecision("deny", "go-policy-denied")
        );

        IllegalArgumentException error = Assertions.assertThrows(
                IllegalArgumentException.class,
                () -> goService.validate(sampleRequest(List.of("search_hotels", "search_transports", "search_attractions")))
        );
        Assertions.assertEquals("go-policy-denied", error.getMessage());
    }

    private TravelRecommendRequest sampleRequest(List<String> tools) {
        return new TravelRecommendRequest(
                "tenant-a", "user-a", "policy-default", "conv-1", "idemp-1",
                "beijing", 3, 3000.0, 2, "basic", List.of("family"),
                10, 10, tools
        );
    }

    private PolicyGuardService.ConfigProvider fixedConfig(Map<String, String> values) {
        return (key, defaultValue) -> values.getOrDefault(key, defaultValue);
    }
}
