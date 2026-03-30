// Package main provides the service entrypoint.
package main

import (
	"math"
	"net/http"
	"os"

	"github.com/gin-gonic/gin"
	json "github.com/goccy/go-json"
)

type ScoreRequest struct {
	Price    float64            `json:"price"`
	Rating   float64            `json:"rating"`
	Duration float64            `json:"duration"`
	Tags     []string           `json:"tags"`
	Budget   float64            `json:"budget"`
	Weights  map[string]float64 `json:"weights"`
}

type ScoreResponse struct {
	Score float64 `json:"score"`
}

func main() {
	gin.SetMode(gin.ReleaseMode)
	r := gin.New()
	r.Use(gin.Recovery())

	r.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": "ok"})
	})

	r.POST("/v1/score/hotel", func(c *gin.Context) {
		var req ScoreRequest
		if err := bindJSON(c, &req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}
		score := hotelScore(req.Price, req.Rating, req.Tags, req.Budget, req.Weights)
		c.JSON(http.StatusOK, ScoreResponse{Score: round(score, 8)})
	})

	r.POST("/v1/score/transport", func(c *gin.Context) {
		var req ScoreRequest
		if err := bindJSON(c, &req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}
		score := transportScore(req.Price, req.Duration, req.Tags, req.Budget, req.Weights)
		c.JSON(http.StatusOK, ScoreResponse{Score: round(score, 8)})
	})

	port := os.Getenv("GO_RANKER_PORT")
	if port == "" {
		port = "8090"
	}
	_ = r.Run(":" + port)
}

func bindJSON(c *gin.Context, target interface{}) error {
	decoder := json.NewDecoder(c.Request.Body)
	decoder.DisallowUnknownFields()
	return decoder.Decode(target)
}

func tagMultiplier(tags []string, weights map[string]float64) float64 {
	score := 1.0
	for _, tag := range tags {
		if w, ok := weights[tag]; ok {
			score *= w
		}
	}
	return score
}

func hotelScore(price float64, rating float64, tags []string, budget float64, weights map[string]float64) float64 {
	priceFactor := math.Min(1.4, budget/math.Max(price, 1.0))
	qualityFactor := rating / 5.0
	return (priceFactor*0.45 + qualityFactor*0.55) * tagMultiplier(tags, weights)
}

func transportScore(price float64, duration float64, tags []string, budget float64, weights map[string]float64) float64 {
	priceFactor := math.Min(1.5, budget/math.Max(price, 1.0))
	speedFactor := 1.0 / math.Max(duration, 0.5)
	return (priceFactor*0.55 + speedFactor*0.45) * tagMultiplier(tags, weights)
}

func round(value float64, precision int) float64 {
	pow := math.Pow(10, float64(precision))
	return math.Round(value*pow) / pow
}
