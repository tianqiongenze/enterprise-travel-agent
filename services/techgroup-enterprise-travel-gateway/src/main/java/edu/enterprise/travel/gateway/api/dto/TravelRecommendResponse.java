package edu.enterprise.travel.gateway.api.dto;

import java.util.List;
import java.util.Map;

/**
 * Unified response returned by gateway after runtime orchestration.
 */
public record TravelRecommendResponse(
        String traceId,
        String aiRationale,
        List<Map<String, Object>> hotelOptions,
        List<Map<String, Object>> transportOptions,
        List<Map<String, Object>> itinerary,
        List<Map<String, Object>> engagementRecommendations,
        List<Map<String, Object>> auditLogs,
        List<Map<String, Object>> a2aLogs
) {
}
