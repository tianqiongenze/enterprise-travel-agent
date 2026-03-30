package edu.enterprise.travel.gateway.api.dto;

/**
 * Standard API error payload.
 */
public record ApiError(
		String code,
		String message,
		String traceId,
		String path,
		long timestamp,
		String suggestion
) {
}
