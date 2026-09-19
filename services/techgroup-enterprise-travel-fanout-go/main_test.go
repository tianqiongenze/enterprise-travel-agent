package main

import (
	"sync"
	"testing"

	"github.com/sony/gobreaker/v2"
)

func TestBreakerForReturnsPersistentInstance(t *testing.T) {
	a := breakerFor("svc-a-http://x")
	b := breakerFor("svc-a-http://x")
	if a != b {
		t.Fatalf("breaker must persist across calls for the same target")
	}
	if a.State() != gobreaker.StateClosed {
		t.Fatalf("fresh breaker must be closed, got %v", a.State())
	}
}

func TestBreakerRegistryConcurrentCreation(t *testing.T) {
	var wg sync.WaitGroup
	instances := make(chan *gobreaker.CircuitBreaker[any], 16)
	for i := 0; i < 16; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			instances <- breakerFor("concurrent-target")
		}()
	}
	wg.Wait()
	close(instances)
	first := <-instances
	for other := range instances {
		if other != first {
			t.Fatalf("concurrent breakerFor calls must resolve to one instance")
		}
	}
}

func TestDispatchHandlesEmptyTargets(t *testing.T) {
	results := dispatch(FanoutRequest{TimeoutMs: 100})
	if len(results) != 0 {
		t.Fatalf("expected zero results for zero targets, got %d", len(results))
	}
}
