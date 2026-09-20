package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/gin-gonic/gin"
)

var testCacheOnce sync.Once

// testRouter returns the production router with the cache initialised exactly
// once for the whole test binary (groupcache panics on duplicate group names).
func testRouter(t *testing.T) *gin.Engine {
	t.Helper()
	testCacheOnce.Do(func() {
		initCache()
	})
	return newRouter()
}

func doJSON(t *testing.T, r *gin.Engine, method string, path string, body string) *httptest.ResponseRecorder {
	t.Helper()
	var reader *bytes.Reader
	if body == "" {
		reader = bytes.NewReader(nil)
	} else {
		reader = bytes.NewReader([]byte(body))
	}
	req := httptest.NewRequest(method, path, reader)
	req.Header.Set("Content-Type", "application/json")
	rec := httptest.NewRecorder()
	r.ServeHTTP(rec, req)
	return rec
}

func TestHealthEndpoint(t *testing.T) {
	rec := doJSON(t, testRouter(t), http.MethodGet, "/health", "")
	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", rec.Code, rec.Body.String())
	}
	var body map[string]string
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatalf("health body must be JSON: %v", err)
	}
	if body["status"] != "ok" {
		t.Fatalf("expected status ok, got %q", body["status"])
	}
}

func TestCacheSetGetRoundTrip(t *testing.T) {
	r := testRouter(t)
	rec := doJSON(t, r, http.MethodPost, "/v1/cache/set", `{"key":"roundtrip","value":"https://ranker:8090"}`)
	if rec.Code != http.StatusOK {
		t.Fatalf("set failed: %d %s", rec.Code, rec.Body.String())
	}
	rec = doJSON(t, r, http.MethodGet, "/v1/cache/get/roundtrip", "")
	if rec.Code != http.StatusOK {
		t.Fatalf("get failed: %d %s", rec.Code, rec.Body.String())
	}
	var got CacheResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &got); err != nil {
		t.Fatalf("get body must be JSON: %v", err)
	}
	if got.Key != "roundtrip" || got.Value != "https://ranker:8090" {
		t.Fatalf("unexpected echo: %+v", got)
	}
	if got.Source != "groupcache" {
		t.Fatalf("expected source groupcache, got %q", got.Source)
	}
}

func TestCacheGetMissReturns404(t *testing.T) {
	rec := doJSON(t, testRouter(t), http.MethodGet, "/v1/cache/get/definitely-missing-key", "")
	if rec.Code != http.StatusNotFound {
		t.Fatalf("expected 404 on miss, got %d: %s", rec.Code, rec.Body.String())
	}
	var body map[string]string
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatalf("miss body must be JSON: %v", err)
	}
	if body["error"] != "miss" {
		t.Fatalf("expected error=miss, got %q", body["error"])
	}
}

func TestCacheSetRejectsUnknownFields(t *testing.T) {
	rec := doJSON(t, testRouter(t), http.MethodPost, "/v1/cache/set", `{"key":"a","value":"b","extra":1}`)
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("expected 400 for unknown field, got %d: %s", rec.Code, rec.Body.String())
	}
}

func TestCacheSetRejectsInvalidAndEmptyBody(t *testing.T) {
	r := testRouter(t)
	for name, body := range map[string]string{
		"invalid json": `{key: value}`,
		"empty body":   "",
	} {
		rec := doJSON(t, r, http.MethodPost, "/v1/cache/set", body)
		if rec.Code != http.StatusBadRequest {
			t.Fatalf("%s: expected 400, got %d: %s", name, rec.Code, rec.Body.String())
		}
	}
}

func TestCacheSetOverwritesExistingKey(t *testing.T) {
	r := testRouter(t)
	key := fmt.Sprintf("overwrite-%d", time.Now().UnixNano())
	if rec := doJSON(t, r, http.MethodPost, "/v1/cache/set", fmt.Sprintf(`{"key":%q,"value":"first"}`, key)); rec.Code != http.StatusOK {
		t.Fatalf("first set failed: %s", rec.Body.String())
	}
	if rec := doJSON(t, r, http.MethodPost, "/v1/cache/set", fmt.Sprintf(`{"key":%q,"value":"second"}`, key)); rec.Code != http.StatusOK {
		t.Fatalf("second set failed: %s", rec.Body.String())
	}
	rec := doJSON(t, r, http.MethodGet, "/v1/cache/get/"+key, "")
	if rec.Code != http.StatusOK {
		t.Fatalf("get after overwrite failed: %d %s", rec.Code, rec.Body.String())
	}
	var got CacheResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &got); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if got.Value != "second" {
		t.Fatalf("expected last write to win, got %q", got.Value)
	}
}

// TestCacheGetExpiredEntryIsDropped covers the TTL expiry branch of the
// getter: an expired entry must answer 404 and be evicted from the store, so
// callers observe a clean miss (the degrade signal) instead of stale data.
func TestCacheGetExpiredEntryIsDropped(t *testing.T) {
	r := testRouter(t)
	key := fmt.Sprintf("expired-%d", time.Now().UnixNano())
	cacheMu.Lock()
	cacheStore[key] = cacheEntry{value: "stale", expiresAt: time.Now().Add(-time.Second)}
	cacheMu.Unlock()

	rec := doJSON(t, r, http.MethodGet, "/v1/cache/get/"+key, "")
	if rec.Code != http.StatusNotFound {
		t.Fatalf("expected 404 for expired entry, got %d: %s", rec.Code, rec.Body.String())
	}
	cacheMu.RLock()
	_, stillThere := cacheStore[key]
	cacheMu.RUnlock()
	if stillThere {
		t.Fatalf("expired entry must be evicted from cacheStore")
	}
}

// TestGetterServesLocalCacheWhenPeerRefreshFails pins the degrade semantics
// shared with the Python runtime registry (real_nacos_registry.py): failures
// while refreshing peers must never block reads from the local cache.
func TestGetterServesLocalCacheWhenPeerRefreshFails(t *testing.T) {
	r := testRouter(t)
	previousErrors := atomic.SwapInt64(&peerRefreshErrors, 7)
	t.Cleanup(func() { atomic.StoreInt64(&peerRefreshErrors, previousErrors) })

	key := fmt.Sprintf("degrade-%d", time.Now().UnixNano())
	if rec := doJSON(t, r, http.MethodPost, "/v1/cache/set", fmt.Sprintf(`{"key":%q,"value":"cached-endpoint"}`, key)); rec.Code != http.StatusOK {
		t.Fatalf("set failed: %s", rec.Body.String())
	}
	rec := doJSON(t, r, http.MethodGet, "/v1/cache/get/"+key, "")
	if rec.Code != http.StatusOK {
		t.Fatalf("peer refresh failures must not break local cache reads, got %d: %s", rec.Code, rec.Body.String())
	}
	var got CacheResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &got); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if got.Value != "cached-endpoint" {
		t.Fatalf("expected cached value despite peer refresh errors, got %+v", got)
	}
}

func TestMetricsEndpointReportsPeerCounters(t *testing.T) {
	previousCount := atomic.SwapInt64(&peerCount, 2)
	previousErrors := atomic.SwapInt64(&peerRefreshErrors, 1)
	t.Cleanup(func() {
		atomic.StoreInt64(&peerCount, previousCount)
		atomic.StoreInt64(&peerRefreshErrors, previousErrors)
	})

	rec := doJSON(t, testRouter(t), http.MethodGet, "/metrics", "")
	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", rec.Code)
	}
	body := rec.Body.String()
	for _, want := range []string{
		"groupcache_peers_count 2\n",
		"groupcache_peer_refresh_timestamp ",
		"groupcache_peer_refresh_errors_total 1\n",
	} {
		if !bytes.Contains(rec.Body.Bytes(), []byte(want)) {
			t.Fatalf("metrics body missing %q: %s", want, body)
		}
	}
}

// TestCacheStoreConcurrentReadWrite exercises parallel setters and getters
// against the shared store; run with -race in CI to catch data races.
func TestCacheStoreConcurrentReadWrite(t *testing.T) {
	r := testRouter(t)
	var wg sync.WaitGroup
	for worker := 0; worker < 8; worker++ {
		wg.Add(1)
		go func(worker int) {
			defer wg.Done()
			for i := 0; i < 25; i++ {
				key := fmt.Sprintf("conc-%d-%d", worker, i%5)
				if worker%2 == 0 {
					body := fmt.Sprintf(`{"key":%q,"value":"v-%d-%d"}`, key, worker, i)
					if rec := doJSON(t, r, http.MethodPost, "/v1/cache/set", body); rec.Code != http.StatusOK {
						t.Errorf("concurrent set failed: %d %s", rec.Code, rec.Body.String())
						return
					}
					continue
				}
				// Getters race with setters: both 200 and 404 are valid
				// outcomes, the point is that no request may panic or hang.
				rec := doJSON(t, r, http.MethodGet, "/v1/cache/get/"+key, "")
				if rec.Code != http.StatusOK && rec.Code != http.StatusNotFound {
					t.Errorf("unexpected status %d for concurrent get", rec.Code)
					return
				}
			}
		}(worker)
	}
	wg.Wait()
}
