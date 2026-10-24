// Package main provides HTTP handler tests for the gin routes
// (/health and /v1/policy/evaluate) using httptest.
package main

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/gin-gonic/gin"
)

func newTestRouter(t *testing.T) *gin.Engine {
	t.Helper()
	if err := initPolicy(); err != nil {
		t.Fatalf("initPolicy: %v", err)
	}
	gin.SetMode(gin.TestMode)
	r := gin.New()
	r.Use(gin.Recovery())
	r.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": "ok"})
	})
	r.POST("/v1/policy/evaluate", func(c *gin.Context) {
		var req PolicyRequest
		if err := bindJSON(c, &req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}
		decision, reason, input := evaluate(req)
		emitDecisionLog(c.GetHeader("X-Trace-Id"), input, decision, reason)
		c.JSON(http.StatusOK, PolicyResponse{Decision: decision, Reason: reason})
	})
	return r
}

func TestHealthEndpoint(t *testing.T) {
	r := newTestRouter(t)
	w := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	r.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("health status = %d, want 200", w.Code)
	}
	if !strings.Contains(w.Body.String(), `"status":"ok"`) {
		t.Fatalf("health body = %q", w.Body.String())
	}
}

func TestEvaluateHandlerAllow(t *testing.T) {
	r := newTestRouter(t)
	body := `{"tenantId":"t1","userId":"u1","idempotencyKey":"k-allow","membershipTier":"gold","orchestrationEngine":"oneagents","allowedTools":["search_hotels","search_events"],"maxAgentSteps":10,"maxToolCalls":10}`
	w := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/v1/policy/evaluate", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Trace-Id", "trace-allow-1")
	r.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("status = %d, body = %s", w.Code, w.Body.String())
	}
	if !strings.Contains(w.Body.String(), `"decision":"allow"`) || !strings.Contains(w.Body.String(), `"reason":"ok"`) {
		t.Fatalf("unexpected body: %s", w.Body.String())
	}
}

func TestEvaluateHandlerDeny(t *testing.T) {
	r := newTestRouter(t)
	body := `{"tenantId":"t1","userId":"u1","idempotencyKey":"k-deny","membershipTier":"gold","orchestrationEngine":"oneagents","allowedTools":["search_hotels","search_events"],"maxAgentSteps":99,"maxToolCalls":10}`
	w := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/v1/policy/evaluate", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	r.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("status = %d, body = %s", w.Code, w.Body.String())
	}
	if !strings.Contains(w.Body.String(), `"decision":"deny"`) {
		t.Fatalf("unexpected body: %s", w.Body.String())
	}
	if !strings.Contains(w.Body.String(), `"reason":"maxAgentSteps exceeds policy limit"`) {
		t.Fatalf("unexpected reason: %s", w.Body.String())
	}
}

func TestEvaluateHandlerRejectsUnknownFields(t *testing.T) {
	r := newTestRouter(t)
	body := `{"tenantId":"t1","bogusField":123}`
	w := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/v1/policy/evaluate", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	r.ServeHTTP(w, req)
	if w.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want 400, body = %s", w.Code, w.Body.String())
	}
}

func TestEvaluateHandlerRejectsMalformedJSON(t *testing.T) {
	r := newTestRouter(t)
	w := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/v1/policy/evaluate", strings.NewReader("{not-json"))
	req.Header.Set("Content-Type", "application/json")
	r.ServeHTTP(w, req)
	if w.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want 400", w.Code)
	}
}

func TestEvaluateHandlerEngineTierMismatch(t *testing.T) {
	r := newTestRouter(t)
	body := `{"tenantId":"t1","userId":"u1","idempotencyKey":"k-tier","membershipTier":"basic","orchestrationEngine":"oneagents","allowedTools":["search_hotels"],"maxAgentSteps":10,"maxToolCalls":10}`
	w := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/v1/policy/evaluate", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	r.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("status = %d", w.Code)
	}
	if !strings.Contains(w.Body.String(), `"decision":"deny"`) {
		t.Fatalf("unexpected body: %s", w.Body.String())
	}
	if !strings.Contains(w.Body.String(), `"reason":"membershipTier cannot use current orchestration engine"`) {
		t.Fatalf("unexpected reason: %s", w.Body.String())
	}
}
