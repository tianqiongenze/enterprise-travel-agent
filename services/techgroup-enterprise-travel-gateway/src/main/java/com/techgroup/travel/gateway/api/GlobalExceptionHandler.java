package com.techgroup.travel.gateway.api;

import com.techgroup.travel.gateway.api.dto.ApiError;
import jakarta.servlet.http.HttpServletRequest;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ControllerAdvice;
import org.springframework.web.bind.annotation.ExceptionHandler;

import java.time.Instant;
import java.util.UUID;

/**
 * Maps gateway exceptions to stable API error payloads.
 */
@ControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ApiError> handleValidation(MethodArgumentNotValidException ex, HttpServletRequest request) {
        String message = ex.getBindingResult().getFieldErrors().stream()
                .findFirst()
                .map(this::toReadableFieldError)
                .orElse("request validation failed");
        return ResponseEntity.badRequest().body(buildError(
                "VALIDATION_ERROR",
                message,
                request,
                "Check request schema and required fields"
        ));
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<ApiError> handlePolicy(IllegalArgumentException ex, HttpServletRequest request) {
        return ResponseEntity.status(HttpStatus.FORBIDDEN).body(buildError(
                "POLICY_VIOLATION",
                ex.getMessage(),
                request,
                "Adjust membership tier, allowedTools, or policy limits"
        ));
    }

    @ExceptionHandler(IllegalStateException.class)
    public ResponseEntity<ApiError> handleDependency(IllegalStateException ex, HttpServletRequest request) {
        return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).body(buildError(
                "DEPENDENCY_UNAVAILABLE",
                ex.getMessage(),
                request,
                "Retry with same idempotencyKey or route to fallback region"
        ));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ApiError> handleGeneric(Exception ex, HttpServletRequest request) {
        log.error("unhandled gateway error on {} {}", request.getMethod(), request.getRequestURI(), ex);
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(buildError(
                        "INTERNAL_ERROR",
                        "internal server error",
                        request,
                        "Contact platform support with traceId"
                ));
    }

    private String toReadableFieldError(FieldError fieldError) {
        return fieldError.getField() + ": " + fieldError.getDefaultMessage();
    }

    private ApiError buildError(String code, String message, HttpServletRequest request, String suggestion) {
        String traceId = request.getHeader("X-Trace-Id");
        if (traceId == null || traceId.isBlank()) {
            traceId = UUID.randomUUID().toString();
        }
        return new ApiError(
                code,
                message,
                traceId,
                request.getRequestURI(),
                Instant.now().toEpochMilli(),
                suggestion
        );
    }
}
