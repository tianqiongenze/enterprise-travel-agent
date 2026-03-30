package edu.enterprise.travel.gateway.api.dto;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;

import java.util.List;

/**
 * API request contract for travel recommendation.
 */
public record TravelRecommendRequest(
        @NotBlank String tenantId,
        @NotBlank String userId,
        @NotBlank String policyId,
        @NotBlank String conversationId,
        @NotBlank String idempotencyKey,
        @NotBlank String city,
        @NotNull @Min(1) Integer days,
        @NotNull @Min(1) Double budget,
        @NotNull @Min(1) Integer travelers,
        String membershipTier,
        @NotNull List<String> preferences,
        @NotNull @Min(1) Integer maxAgentSteps,
        @NotNull @Min(1) Integer maxToolCalls,
        @NotEmpty List<String> allowedTools
) {
}
