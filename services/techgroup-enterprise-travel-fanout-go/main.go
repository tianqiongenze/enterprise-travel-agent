// Package main provides the fanout service entrypoint.
package main

import (
	"bytes"
	"context"
	"errors"
	"net/http"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"

	"github.com/gin-gonic/gin"
	json "github.com/goccy/go-json"
	"github.com/sony/gobreaker/v2"
	"golang.org/x/sync/errgroup"
	"golang.org/x/sync/singleflight"
)

type FanoutRequest struct {
	ID        string         `json:"id"`
	Targets   []FanoutTarget `json:"targets"`
	Payload   map[string]any `json:"payload"`
	TimeoutMs int            `json:"timeoutMs"`
}

type FanoutTarget struct {
	Name   string `json:"name"`
	URL    string `json:"url"`
	Method string `json:"method"`
}

type FanoutResponse struct {
	Results []FanoutResult `json:"results"`
}

type FanoutResult struct {
	Target  string `json:"target"`
	Status  int    `json:"status"`
	Latency int64  `json:"latencyMs"`
	Error   string `json:"error"`
}

var (
	sf              singleflight.Group
	breakerRegistry sync.Map // key string -> *gobreaker.CircuitBreaker[any]
	outboundClient  = &http.Client{
		// Outbound calls also inherit the per-request context timeout; these
		// are hard transport ceilings so a slow target can never pin a worker.
		Timeout: 5 * time.Second,
		Transport: &http.Transport{
			MaxIdleConns:        200,
			MaxIdleConnsPerHost: 50,
			IdleConnTimeout:     60 * time.Second,
		},
	}
)

// breakerFor returns the persistent circuit breaker for a target. Creating the
// breaker per request was a defect: breaker state (failure counts, open state)
// never accumulated, so the protection was a no-op.
func breakerFor(name string) *gobreaker.CircuitBreaker[any] {
	if cached, ok := breakerRegistry.Load(name); ok {
		return cached.(*gobreaker.CircuitBreaker[any])
	}
	created := gobreaker.NewCircuitBreaker[any](gobreaker.Settings{
		Name:        name,
		MaxRequests: 2,                // half-open probes after cooldown
		Interval:    30 * time.Second, // failure window
		Timeout:     20 * time.Second, // open cooldown
	})
	actual, _ := breakerRegistry.LoadOrStore(name, created)
	return actual.(*gobreaker.CircuitBreaker[any])
}

func main() {
	gin.SetMode(gin.ReleaseMode)
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
		results := dispatch(req)
		c.JSON(http.StatusOK, FanoutResponse{Results: results})
	})

	port := os.Getenv("GO_FANOUT_PORT")
	if port == "" {
		port = "8092"
	}

	server := &http.Server{
		Addr:              ":" + port,
		Handler:           r,
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       15 * time.Second,
		WriteTimeout:      30 * time.Second,
		IdleTimeout:       60 * time.Second,
	}

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	go func() {
		<-ctx.Done()
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		_ = server.Shutdown(shutdownCtx)
	}()

	if err := server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		os.Exit(1)
	}
}

func bindJSON(c *gin.Context, target interface{}) error {
	decoder := json.NewDecoder(c.Request.Body)
	decoder.DisallowUnknownFields()
	return decoder.Decode(target)
}

func dispatch(req FanoutRequest) []FanoutResult {
	if req.TimeoutMs <= 0 {
		req.TimeoutMs = 800
	}
	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(req.TimeoutMs)*time.Millisecond)
	defer cancel()

	results := make([]FanoutResult, len(req.Targets))
	g, ctx := errgroup.WithContext(ctx)

	for i, target := range req.Targets {
		i := i
		target := target
		g.Go(func() error {
			start := time.Now()
			status, errMsg := callTarget(ctx, outboundClient, target, req.Payload)
			results[i] = FanoutResult{
				Target:  target.Name,
				Status:  status,
				Latency: time.Since(start).Milliseconds(),
				Error:   errMsg,
			}
			return nil
		})
	}
	_ = g.Wait()
	return results
}

func callTarget(ctx context.Context, client *http.Client, target FanoutTarget, payload map[string]any) (int, string) {
	body, _ := json.Marshal(payload)
	method := target.Method
	if method == "" {
		method = http.MethodPost
	}
	cb := breakerFor("fanout-" + target.Name + "-" + target.URL)

	key := target.Name + "::" + target.URL + "::" + string(body)
	v, err, _ := sf.Do(key, func() (any, error) {
		result, cbErr := cb.Execute(func() (any, error) {
			request, reqErr := http.NewRequestWithContext(ctx, method, target.URL, bytes.NewReader(body))
			if reqErr != nil {
				return 0, reqErr
			}
			request.Header.Set("Content-Type", "application/json")
			response, doErr := client.Do(request)
			if doErr != nil {
				return 0, doErr
			}
			defer response.Body.Close()
			return response.StatusCode, nil
		})
		if cbErr != nil {
			return 0, cbErr
		}
		return result, nil
	})
	if err != nil {
		return 0, err.Error()
	}
	status, ok := v.(int)
	if !ok {
		return 0, "fanout status parse failure"
	}
	return status, ""
}
