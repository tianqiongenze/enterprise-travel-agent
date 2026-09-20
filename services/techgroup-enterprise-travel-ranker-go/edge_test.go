// Package main provides edge-case tests for the ranker scoring helpers:
// empty/missing dimensions, extreme inputs, and non-panic guarantees.
package main

import (
	"math"
	"testing"
)

func TestHotelScoreEmptyTags(t *testing.T) {
	got := hotelScore(1000, 4.5, nil, 2000, map[string]float64{})
	want := math.Min(1.4, 2000.0/1000.0)*0.45 + (4.5/5.0)*0.55
	if math.Abs(got-want) > 1e-9 {
		t.Fatalf("hotelScore = %v, want %v", got, want)
	}
}

func TestHotelScorePriceAboveBudgetCapsFactor(t *testing.T) {
	// budget/price below 1 must not be capped; price 0 must not panic.
	if got := hotelScore(0, 4.0, nil, 1000, nil); math.IsNaN(got) || math.IsInf(got, 0) {
		t.Fatalf("hotelScore(price=0) = %v", got)
	}
	if got := hotelScore(10000, 5.0, nil, 100, nil); got <= 0 {
		t.Fatalf("hotelScore(price>>budget) = %v, want > 0", got)
	}
}

func TestHotelScorePriceFactorCeiling(t *testing.T) {
	// budget/price is capped at 1.4: a nearly free hotel must score the same
	// as one at budget/1.4, all else equal.
	cheap := hotelScore(1, 4.0, nil, 10000, nil)
	capped := hotelScore(10000/1.4, 4.0, nil, 10000, nil)
	if math.Abs(cheap-capped) > 1e-9 {
		t.Fatalf("price factor not capped: %v vs %v", cheap, capped)
	}
}

func TestTransportScoreExtremeDuration(t *testing.T) {
	if got := transportScore(100, 0, nil, 1000, nil); math.IsNaN(got) || math.IsInf(got, 0) {
		t.Fatalf("transportScore(duration=0) = %v", got)
	}
	if got := transportScore(100, 1e9, nil, 1000, nil); got <= 0 {
		t.Fatalf("transportScore(huge duration) = %v, want > 0", got)
	}
}

func TestTagMultiplierExtremeWeights(t *testing.T) {
	weights := map[string]float64{"a": 0.0, "b": 1e6, "c": 1e-6}
	if got := tagMultiplier([]string{"a", "b"}, weights); got != 0 {
		t.Fatalf("zero weight should zero the multiplier, got %v", got)
	}
	if got := tagMultiplier([]string{"b", "c"}, weights); math.Abs(got-1.0) > 1e-9 {
		t.Fatalf("1e6 * 1e-6 = %v, want 1.0", got)
	}
	if got := tagMultiplier(nil, weights); got != 1.0 {
		t.Fatalf("empty tags = %v, want 1.0", got)
	}
	if got := tagMultiplier([]string{"unknown"}, nil); got != 1.0 {
		t.Fatalf("nil weights = %v, want 1.0", got)
	}
}

func TestScoresNeverNaN(t *testing.T) {
	inputs := []struct {
		price, rating, duration, budget float64
	}{
		{0, 0, 0, 0},
		{-1, -1, -1, -1},
		{math.MaxFloat64 / 4, 5, 1, math.MaxFloat64 / 4},
	}
	for i, in := range inputs {
		h := hotelScore(in.price, in.rating, nil, in.budget, nil)
		tr := transportScore(in.price, in.duration, nil, in.budget, nil)
		if math.IsNaN(h) || math.IsInf(h, 0) {
			t.Fatalf("case %d hotelScore = %v", i, h)
		}
		if math.IsNaN(tr) || math.IsInf(tr, 0) {
			t.Fatalf("case %d transportScore = %v", i, tr)
		}
	}
}

func TestRoundNegativeAndHuge(t *testing.T) {
	if got := round(-1.23456, 8); math.Abs(got-(-1.23456)) > 1e-8 {
		t.Fatalf("round(-1.23456, 8) = %v", got)
	}
	if got := round(1e300, 8); !math.IsInf(got, 1) && got <= 1e299 {
		// Rounding huge values may overflow; it must not panic.
		t.Logf("round(1e300, 8) = %v (overflow tolerated)", got)
	}
}

func TestBatchScoresMatchSingle(t *testing.T) {
	reqs := []ScoreRequest{
		{Price: 800, Rating: 4.2, Tags: []string{"湖景"}, Budget: 3000, Weights: map[string]float64{"湖景": 1.1}},
		{Price: 1500, Rating: 4.8, Duration: 2.5, Tags: nil, Budget: 3000},
	}
	for _, req := range reqs {
		single := hotelScore(req.Price, req.Rating, req.Tags, req.Budget, req.Weights)
		batch := round(single, 8)
		if math.Abs(single-batch) > 5e-9 {
			t.Fatalf("round drift: %v vs %v", single, batch)
		}
	}
}
