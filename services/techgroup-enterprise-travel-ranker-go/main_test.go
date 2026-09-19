package main

import (
	"math"
	"testing"
)

func TestHotelScoreOrdersByQualityAndPrice(t *testing.T) {
	weights := map[string]float64{"family": 1.1}
	cheapGood := hotelScore(300, 4.8, []string{"family"}, 3000, weights)
	expensivePoor := hotelScore(2500, 3.0, nil, 3000, weights)
	if cheapGood <= expensivePoor {
		t.Fatalf("expected cheap+good hotel to outrank expensive+poor: %v vs %v", cheapGood, expensivePoor)
	}
	if cheapGood > 1.4*1.1 { // priceFactor ceiling * tag multiplier
		t.Fatalf("score exceeded theoretical ceiling: %v", cheapGood)
	}
}

func TestHotelScoreZeroPriceDoesNotPanic(t *testing.T) {
	score := hotelScore(0, 4.0, nil, 1000, nil)
	if math.IsNaN(score) || math.IsInf(score, 0) {
		t.Fatalf("score must be finite, got %v", score)
	}
}

func TestTransportScorePrefersCheaperFaster(t *testing.T) {
	fast := transportScore(100, 1.0, nil, 1000, nil)
	slow := transportScore(500, 10.0, nil, 1000, nil)
	if fast <= slow {
		t.Fatalf("expected faster+cheaper transport to outrank: %v vs %v", fast, slow)
	}
}

func TestTagMultiplierAppliesWeights(t *testing.T) {
	if got := tagMultiplier([]string{"family", "comfort"}, map[string]float64{"family": 1.1, "comfort": 0.9}); math.Abs(got-0.99) > 1e-9 {
		t.Fatalf("expected 0.99 multiplier, got %v", got)
	}
	if got := tagMultiplier([]string{"unknown"}, nil); got != 1.0 {
		t.Fatalf("unknown tags must not change the score, got %v", got)
	}
}

func TestRoundPrecision(t *testing.T) {
	if got := round(0.123456789, 8); math.Abs(got-0.12345679) > 1e-9 {
		t.Fatalf("round precision wrong: %v", got)
	}
}

func TestBatchScoreConsistency(t *testing.T) {
	items := []ScoreRequest{
		{Price: 300, Rating: 4.8, Budget: 3000},
		{Price: 2500, Rating: 3.0, Budget: 3000},
	}
	scores := make([]float64, 0, len(items))
	for _, item := range items {
		scores = append(scores, round(hotelScore(item.Price, item.Rating, item.Tags, item.Budget, item.Weights), 8))
	}
	if len(scores) != len(items) {
		t.Fatalf("expected %d scores, got %d", len(items), len(scores))
	}
	if scores[0] <= scores[1] {
		t.Fatalf("expected descending order by quality/price, got %v", scores)
	}
}
