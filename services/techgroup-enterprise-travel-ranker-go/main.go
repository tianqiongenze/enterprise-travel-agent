// Package main provides the service entrypoint.
package main

import (
	"context"
	"errors"
	"fmt"
	"math"
	"net"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gin-gonic/gin"
	json "github.com/goccy/go-json"
	travelgrpcv1 "github.com/techgroup/enterprise-travel-agent/techgroup-enterprise-travel-ranker-go/internal/grpcgen/v1"
	"google.golang.org/grpc"
	"google.golang.org/grpc/keepalive"
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

type BatchScoreRequest struct {
	Items []ScoreRequest `json:"items"`
}

type BatchScoreResponse struct {
	Scores []float64 `json:"scores"`
}

type rankerGRPCServer struct {
	travelgrpcv1.UnimplementedRankerServiceServer
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

	r.POST("/v1/score/hotel/batch", func(c *gin.Context) {
		var req BatchScoreRequest
		if err := bindJSON(c, &req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}
		scores := make([]float64, 0, len(req.Items))
		for _, item := range req.Items {
			score := hotelScore(item.Price, item.Rating, item.Tags, item.Budget, item.Weights)
			scores = append(scores, round(score, 8))
		}
		c.JSON(http.StatusOK, BatchScoreResponse{Scores: scores})
	})

	r.POST("/v1/score/transport/batch", func(c *gin.Context) {
		var req BatchScoreRequest
		if err := bindJSON(c, &req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}
		scores := make([]float64, 0, len(req.Items))
		for _, item := range req.Items {
			score := transportScore(item.Price, item.Duration, item.Tags, item.Budget, item.Weights)
			scores = append(scores, round(score, 8))
		}
		c.JSON(http.StatusOK, BatchScoreResponse{Scores: scores})
	})

	port := os.Getenv("GO_RANKER_PORT")
	if port == "" {
		port = "8090"
	}
	grpcPort := os.Getenv("GO_RANKER_GRPC_PORT")
	if grpcPort == "" {
		grpcPort = "9090"
	}

	httpServer := &http.Server{
		Addr:              ":" + port,
		Handler:           r,
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       10 * time.Second,
		WriteTimeout:      15 * time.Second,
		IdleTimeout:       60 * time.Second,
	}

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	grpcDone := make(chan error, 1)
	go func() {
		grpcDone <- runGRPC(grpcPort)
	}()
	httpDone := make(chan error, 1)
	go func() {
		httpDone <- httpServer.ListenAndServe()
	}()

	select {
	case <-ctx.Done():
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		_ = httpServer.Shutdown(shutdownCtx)
		grpcServer.GracefulStop()
	case err := <-httpDone:
		if err != nil && !errors.Is(err, http.ErrServerClosed) {
			os.Exit(1)
		}
	case err := <-grpcDone:
		if err != nil {
			os.Exit(1)
		}
	}
}

var grpcServer *grpc.Server

func runGRPC(port string) error {
	listener, err := net.Listen("tcp", ":"+port)
	if err != nil {
		return fmt.Errorf("listen grpc :%s failed: %w", port, err)
	}
	grpcServer = grpc.NewServer(
		grpc.KeepaliveParams(keepalive.ServerParameters{
			Time:    30 * time.Second,
			Timeout: 10 * time.Second,
		}),
	)
	travelgrpcv1.RegisterRankerServiceServer(grpcServer, &rankerGRPCServer{})
	return grpcServer.Serve(listener)
}

func (s *rankerGRPCServer) ScoreHotel(_ context.Context, req *travelgrpcv1.ScoreRequest) (*travelgrpcv1.ScoreResponse, error) {
	score := hotelScore(req.Price, req.Rating, req.Tags, req.Budget, req.Weights)
	return &travelgrpcv1.ScoreResponse{Score: round(score, 8)}, nil
}

func (s *rankerGRPCServer) ScoreTransport(_ context.Context, req *travelgrpcv1.ScoreRequest) (*travelgrpcv1.ScoreResponse, error) {
	score := transportScore(req.Price, req.Duration, req.Tags, req.Budget, req.Weights)
	return &travelgrpcv1.ScoreResponse{Score: round(score, 8)}, nil
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
