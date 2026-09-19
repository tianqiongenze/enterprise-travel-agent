package com.techgroup.travel.gateway.api;

import com.techgroup.travel.gateway.api.dto.TravelRecommendRequest;
import com.techgroup.travel.gateway.api.dto.TravelRecommendResponse;
import com.techgroup.travel.gateway.service.PolicyGuardService;
import com.techgroup.travel.gateway.service.PulsarAuditMirrorService;
import com.techgroup.travel.gateway.service.PythonRuntimeClient;
import com.techgroup.travel.gateway.service.SpringAiAlibabaAdvisorService;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * Public gateway API for travel recommendation calls.
 */
@RestController
@RequestMapping("/api/v1/travel")
public class TravelGatewayController {

    private final PolicyGuardService policyGuardService;
    private final PythonRuntimeClient pythonRuntimeClient;
    private final SpringAiAlibabaAdvisorService springAiAlibabaAdvisorService;
    private final PulsarAuditMirrorService pulsarAuditMirrorService;

    public TravelGatewayController(
            PolicyGuardService policyGuardService,
            PythonRuntimeClient pythonRuntimeClient,
            SpringAiAlibabaAdvisorService springAiAlibabaAdvisorService,
            PulsarAuditMirrorService pulsarAuditMirrorService
    ) {
        this.policyGuardService = policyGuardService;
        this.pythonRuntimeClient = pythonRuntimeClient;
        this.springAiAlibabaAdvisorService = springAiAlibabaAdvisorService;
        this.pulsarAuditMirrorService = pulsarAuditMirrorService;
    }

    /**
     * Lightweight health endpoint for gateway probes.
     */
    @GetMapping("/health")
    public ResponseEntity<Map<String, String>> health() {
        return ResponseEntity.ok(Map.of("status", "ok"));
    }

    /**
     * Returns policy cache metrics used by ops dashboards.
     */
    @GetMapping("/policy/cache/stats")
    public ResponseEntity<Map<String, Object>> policyCacheStats() {
        return ResponseEntity.ok(policyGuardService.cacheStats());
    }

    /**
     * Main recommendation endpoint: validates policy, calls runtime, mirrors audit, and enriches rationale.
     */
    @PostMapping("/recommend")
    public ResponseEntity<TravelRecommendResponse> recommend(
            @Valid @RequestBody TravelRecommendRequest request,
            @RequestHeader(value = "X-Trace-Id", required = false) String traceId
    ) {
        policyGuardService.validate(request);
        String effectiveTraceId = traceId == null || traceId.isBlank() ? UUID.randomUUID().toString() : traceId;
        Map<String, Object> result = pythonRuntimeClient.recommend(request, effectiveTraceId);
        pulsarAuditMirrorService.publishAsync(effectiveTraceId, request.city(), request.tenantId(), result);
        String aiRationale = springAiAlibabaAdvisorService.buildRationale(request);
        return ResponseEntity.ok(new TravelRecommendResponse(
                effectiveTraceId,
                aiRationale,
                getList(result, "hotel_options"),
                getList(result, "transport_options"),
                getList(result, "itinerary"),
                getList(result, "engagement_recommendations"),
                getList(result, "audit_logs"),
                getList(result, "a2a_logs")
        ));
    }

    @SuppressWarnings("unchecked")
    private List<Map<String, Object>> getList(Map<String, Object> payload, String key) {
        Object value = payload.get(key);
        if (value == null) {
            return List.of();
        }
        return (List<Map<String, Object>>) value;
    }
}
