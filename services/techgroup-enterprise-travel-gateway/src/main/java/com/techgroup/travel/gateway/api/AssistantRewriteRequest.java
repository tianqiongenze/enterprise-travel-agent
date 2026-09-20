package com.techgroup.travel.gateway.api;

import jakarta.validation.constraints.NotBlank;

/**
 * Request contract for the assistant rewrite endpoint.
 */
public record AssistantRewriteRequest(
        @NotBlank String text,
        String city
) {
}
