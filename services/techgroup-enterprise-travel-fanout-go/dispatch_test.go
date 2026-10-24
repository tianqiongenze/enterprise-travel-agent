// Package main provides dispatch partial-failure tests using httptest
// targets: one healthy endpoint plus slow/erroring/unreachable targets.
package main

import (
	"context"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/gin-gonic/gin"
)

func newRequestContext(t *testing.T) context.Context {
	t.Helper()
	return context.Background()
}

func newFanoutTestRouter() *gin.Engine {
	gin.SetMode(gin.TestMode)
	r := gin.New()
	r.Use(gin.Recovery())
	r.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": "ok"})
	})
	r.POST("/v1/fanout/dispatch", func(c *gin.Context) {
		var req FanoutRequest
		if err := bindJSON(c, &req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}
		c.JSON(http.StatusOK, FanoutResponse{Results: dispatch(req)})
	})
	return r
}

func TestDispatchPartialFailure(t *testing.T) {
	ok := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	defer ok.Close()
	bad := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer bad.Close()

	results := dispatch(FanoutRequest{
		ID:        "partial-1",
		TimeoutMs: 1000,
		Payload:   map[string]any{"ping": 1},
		Targets: []FanoutTarget{
			{Name: "ok", URL: ok.URL, Method: http.MethodPost},
			{Name: "bad", URL: bad.URL, Method: http.MethodPost},
			{Name: "down", URL: "http://127.0.0.1:1/unreachable", Method: http.MethodPost},
		},
	})

	if len(results) != 3 {
		t.Fatalf("results len = %d, want 3", len(results))
	}
	byName := map[string]FanoutResult{}
	for _, r := range results {
		byName[r.Target] = r
	}
	if byName["ok"].Status != http.StatusOK || byName["ok"].Error != "" {
		t.Fatalf("ok target: %+v", byName["ok"])
	}
	if byName["bad"].Status != http.StatusInternalServerError {
		t.Fatalf("bad target status = %d, want 500", byName["bad"].Status)
	}
	if byName["down"].Error == "" {
		t.Fatal("unreachable target must carry an error")
	}
}

func TestDispatchSlowTargetRespectsTimeout(t *testing.T) {
	slow := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(700 * time.Millisecond)
		w.WriteHeader(http.StatusOK)
	}))
	defer slow.Close()

	start := time.Now()
	results := dispatch(FanoutRequest{
		ID:        "slow-1",
		TimeoutMs: 150,
		Targets:   []FanoutTarget{{Name: "slow", URL: slow.URL, Method: http.MethodPost}},
	})
	elapsed := time.Since(start)
	if elapsed > 3*time.Second {
		t.Fatalf("dispatch took %v, timeout not enforced", elapsed)
	}
	if len(results) != 1 || results[0].Error == "" {
		t.Fatalf("slow target should surface an error, got %+v", results)
	}
}

func TestDispatchEmptyTargets(t *testing.T) {
	results := dispatch(FanoutRequest{ID: "empty", TimeoutMs: 100})
	if results == nil || len(results) != 0 {
		t.Fatalf("empty targets should return empty slice, got %+v", results)
	}
}

func TestCallTargetGetMethod(t *testing.T) {
	var seenMethod string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seenMethod = r.Method
		w.WriteHeader(http.StatusAccepted)
	}))
	defer srv.Close()

	status, errMsg := callTarget(newRequestContext(t), outboundClient, FanoutTarget{Name: "m", URL: srv.URL, Method: http.MethodGet}, nil)
	if errMsg != "" || status != http.StatusAccepted {
		t.Fatalf("status=%d err=%q", status, errMsg)
	}
	if seenMethod != http.MethodGet {
		t.Fatalf("method = %s, want GET", seenMethod)
	}
}

func TestHandlerMalformedBody(t *testing.T) {
	ginRouter := newFanoutTestRouter()
	w := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/v1/fanout/dispatch", strings.NewReader("{bad"))
	req.Header.Set("Content-Type", "application/json")
	ginRouter.ServeHTTP(w, req)
	if w.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want 400", w.Code)
	}
}
