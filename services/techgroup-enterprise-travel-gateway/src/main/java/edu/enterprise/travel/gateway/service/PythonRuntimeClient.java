package edu.enterprise.travel.gateway.service;

import edu.enterprise.travel.gateway.api.dto.TravelRecommendRequest;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.web.client.RestTemplateBuilder;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

/**
 * Client used by gateway to call the internal Python runtime recommendation API.
 */
@Component
public class PythonRuntimeClient {

    private final RestTemplate restTemplate;
    private final String baseUrl;
    private final InternalTokenService internalTokenService;
    private final String mtlsClientId;

    public PythonRuntimeClient(
            RestTemplateBuilder builder,
            @Value("${travel.runtime.base-url}") String baseUrl,
            @Value("${travel.internal.mtls-client-id}") String mtlsClientId,
            InternalTokenService internalTokenService
    ) {
        SimpleClientHttpRequestFactory requestFactory = new SimpleClientHttpRequestFactory();
        requestFactory.setConnectTimeout(2000);
        requestFactory.setReadTimeout(15000);
        this.restTemplate = builder
                .requestFactory(() -> requestFactory)
                .build();
        this.baseUrl = baseUrl;
        this.mtlsClientId = mtlsClientId;
        this.internalTokenService = internalTokenService;
    }

    /**
     * Testing constructor to avoid full Spring wiring.
     */
    PythonRuntimeClient(RestTemplate restTemplate, String baseUrl, String mtlsClientId, InternalTokenService internalTokenService) {
        this.restTemplate = restTemplate;
        this.baseUrl = baseUrl;
        this.mtlsClientId = mtlsClientId;
        this.internalTokenService = internalTokenService;
    }

    /**
     * Calls `/runtime/recommend` and returns the runtime payload.
     */
    public Map<String, Object> recommend(TravelRecommendRequest request, String traceId) {
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
        payload.put("membershipTier", request.membershipTier());
        payload.put("preferences", request.preferences());
        payload.put("maxAgentSteps", request.maxAgentSteps());
        payload.put("maxToolCalls", request.maxToolCalls());
        payload.put("allowedTools", request.allowedTools());

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.add("X-Trace-Id", traceId == null || traceId.isBlank() ? UUID.randomUUID().toString() : traceId);
        headers.add("traceparent", "00-" + UUID.randomUUID().toString().replace("-", "") + "-0000000000000001-01");
        headers.add("X-Internal-Client-Id", mtlsClientId);
        headers.add("X-Internal-Signature", internalTokenService.sign(request.idempotencyKey()));

        ResponseEntity<Map<String, Object>> response = restTemplate.exchange(
                baseUrl + "/runtime/recommend",
                HttpMethod.POST,
                new HttpEntity<>(payload, headers),
                new ParameterizedTypeReference<>() {
                }
        );
        Map<String, Object> body = response.getBody();
        if (body == null) {
            throw new IllegalStateException("runtime response is empty");
        }
        return body;
    }
}
