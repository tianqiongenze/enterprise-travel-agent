// Package main provides the service entrypoint.
package main

import (
	"bytes"
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"net/http"
	"os"
	"strconv"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
	json "github.com/goccy/go-json"
	"github.com/open-policy-agent/opa/rego"
)

type PolicyRequest struct {
	TenantID       string   `json:"tenantId"`
	UserID         string   `json:"userId"`
	PolicyID       string   `json:"policyId"`
	ConversationID string   `json:"conversationId"`
	IdempotencyKey string   `json:"idempotencyKey"`
	City           string   `json:"city"`
	Days           int      `json:"days"`
	Budget         float64  `json:"budget"`
	Travelers      int      `json:"travelers"`
	MembershipTier string   `json:"membershipTier"`
	OrchestrationEngine string `json:"orchestrationEngine"`
	Preferences    []string `json:"preferences"`
	MaxAgentSteps  int      `json:"maxAgentSteps"`
	MaxToolCalls   int      `json:"maxToolCalls"`
	AllowedTools   []string `json:"allowedTools"`
}

type PolicyResponse struct {
	Decision string `json:"decision"`
	Reason   string `json:"reason"`
}

type DecisionLog struct {
	DecisionID  string                 `json:"decision_id"`
	Timestamp   string                 `json:"timestamp"`
	Input       map[string]any         `json:"input"`
	Decision    string                 `json:"decision"`
	Reason      string                 `json:"reason"`
	PolicyPath  string                 `json:"policy_path"`
	Signature   string                 `json:"signature"`
}

var preparedAllow rego.PreparedEvalQuery
var preparedReason rego.PreparedEvalQuery
var decisionLogQueue chan DecisionLog
var decisionCache sync.Map

type cachedPolicyDecision struct {
	decision string
	reason   string
	expires  int64
}

func main() {
	if err := initPolicy(); err != nil {
		panic(err)
	}
	initDecisionLogWorkers()

	gin.SetMode(gin.ReleaseMode)
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

	port := os.Getenv("GO_POLICY_PORT")
	if port == "" {
		port = "8091"
	}
	_ = r.Run(":" + port)
}

func initPolicy() error {
	ctx := context.Background()
	allowQuery, err := rego.New(
		rego.Query("data.authz.allow"),
		rego.Load([]string{"./policy.rego"}, nil),
	).PrepareForEval(ctx)
	if err != nil {
		return err
	}
	reasonQuery, err := rego.New(
		rego.Query("data.authz.reason"),
		rego.Load([]string{"./policy.rego"}, nil),
	).PrepareForEval(ctx)
	if err != nil {
		return err
	}
	preparedAllow = allowQuery
	preparedReason = reasonQuery
	return nil
}

func bindJSON(c *gin.Context, target interface{}) error {
	decoder := json.NewDecoder(c.Request.Body)
	decoder.DisallowUnknownFields()
	return decoder.Decode(target)
}

func evaluate(req PolicyRequest) (string, string, map[string]any) {
	ctx := context.Background()
	cacheKey := req.TenantID + "|" + req.UserID + "|" + req.IdempotencyKey + "|" + req.PolicyID
	if cached, ok := loadCachedDecision(cacheKey); ok {
		input := map[string]any{
			"tenantId": req.TenantID,
			"userId":   req.UserID,
		}
		return cached.decision, cached.reason, input
	}
	input := map[string]any{
		"tenantId":       req.TenantID,
		"userId":         req.UserID,
		"policyId":       req.PolicyID,
		"conversationId": req.ConversationID,
		"idempotencyKey": req.IdempotencyKey,
		"city":           req.City,
		"days":           req.Days,
		"budget":         req.Budget,
		"travelers":      req.Travelers,
		"membershipTier": req.MembershipTier,
		"orchestrationEngine": policyCoreNormalizeEngine(req.OrchestrationEngine),
		"preferences":    req.Preferences,
		"maxAgentSteps":  req.MaxAgentSteps,
		"maxToolCalls":   req.MaxToolCalls,
		"allowedTools":   req.AllowedTools,
	}
	allowResults, err := preparedAllow.Eval(ctx, rego.EvalInput(input))
	if err != nil || len(allowResults) == 0 || len(allowResults[0].Expressions) == 0 {
		return "deny", "policy evaluation error", input
	}
	allow, ok := allowResults[0].Expressions[0].Value.(bool)
	if !ok {
		return "deny", "invalid policy decision", input
	}
	reasonResults, reasonErr := preparedReason.Eval(ctx, rego.EvalInput(input))
	reason := "policy denied"
	if reasonErr == nil && len(reasonResults) > 0 && len(reasonResults[0].Expressions) > 0 {
		if value, castOk := reasonResults[0].Expressions[0].Value.(string); castOk {
			reason = value
		}
	}
	if allow {
		storeCachedDecision(cacheKey, "allow", reason)
		return "allow", reason, input
	}
	storeCachedDecision(cacheKey, "deny", reason)
	return "deny", reason, input
}

func emitDecisionLog(decisionID string, input map[string]any, decision string, reason string) {
	if decisionID == "" {
		decisionID = "policy-" + time.Now().Format("20060102150405.000")
	}
	maskedInput := maskInput(input)
	entry := DecisionLog{
		DecisionID: decisionID,
		Timestamp:  time.Now().UTC().Format(time.RFC3339Nano),
		Input:      maskedInput,
		Decision:   decision,
		Reason:     reason,
		PolicyPath: "data.authz.allow",
	}
	entry.Signature = signDecisionLog(entry)
	if decisionLogQueue != nil {
		select {
		case decisionLogQueue <- entry:
			return
		default:
			println("[go-policy] decision log queue full, fallback direct send")
		}
	}
	deliverDecisionLog(entry)
}

func initDecisionLogWorkers() {
	queueSize := envInt("GO_POLICY_LOG_QUEUE_SIZE", 2048)
	workers := envInt("GO_POLICY_LOG_WORKERS", 2)
	decisionLogQueue = make(chan DecisionLog, maxInt(64, queueSize))
	for i := 0; i < maxInt(1, workers); i++ {
		go func() {
			for entry := range decisionLogQueue {
				deliverDecisionLog(entry)
			}
		}()
	}
}

func deliverDecisionLog(entry DecisionLog) {
	body, err := json.Marshal(entry)
	if err != nil {
		return
	}
	endpoint := os.Getenv("GO_POLICY_DECISION_LOG_ENDPOINT")
	if endpoint == "" {
		println(string(body))
		return
	}
	client := &http.Client{Timeout: 1500 * time.Millisecond}
	request, reqErr := http.NewRequest(http.MethodPost, endpoint, bytes.NewReader(body))
	if reqErr != nil {
		println(string(body))
		return
	}
	request.Header.Set("Content-Type", "application/json")
	response, doErr := client.Do(request)
	if doErr != nil {
		println(string(body))
		return
	}
	if response != nil && response.Body != nil {
		_ = response.Body.Close()
	}
}

func loadCachedDecision(cacheKey string) (cachedPolicyDecision, bool) {
	value, ok := decisionCache.Load(cacheKey)
	if !ok {
		return cachedPolicyDecision{}, false
	}
	row, castOK := value.(cachedPolicyDecision)
	if !castOK {
		decisionCache.Delete(cacheKey)
		return cachedPolicyDecision{}, false
	}
	if time.Now().UnixMilli() > row.expires {
		decisionCache.Delete(cacheKey)
		return cachedPolicyDecision{}, false
	}
	return row, true
}

func storeCachedDecision(cacheKey string, decision string, reason string) {
	ttlMs := envInt("GO_POLICY_CACHE_TTL_MS", 5000)
	decisionCache.Store(cacheKey, cachedPolicyDecision{
		decision: decision,
		reason:   reason,
		expires:  time.Now().Add(time.Duration(maxInt(500, ttlMs)) * time.Millisecond).UnixMilli(),
	})
}

func envInt(name string, fallback int) int {
	value := os.Getenv(name)
	if value == "" {
		return fallback
	}
	parsed, err := strconv.Atoi(value)
	if err != nil {
		return fallback
	}
	return parsed
}

func maxInt(a int, b int) int {
	if a > b {
		return a
	}
	return b
}

func maskInput(input map[string]any) map[string]any {
	masked := map[string]any{}
	for key, value := range input {
		switch key {
		case "userId", "tenantId", "conversationId", "idempotencyKey":
			masked[key] = "***"
		default:
			masked[key] = value
		}
	}
	return masked
}

func signDecisionLog(entry DecisionLog) string {
	secret := os.Getenv("GO_POLICY_DECISION_LOG_SIGNING_KEY")
	if secret == "" {
		return ""
	}
	raw := entry.DecisionID + "|" + entry.Timestamp + "|" + entry.Decision + "|" + entry.Reason
	mac := hmac.New(sha256.New, []byte(secret))
	_, _ = mac.Write([]byte(raw))
	return hex.EncodeToString(mac.Sum(nil))
}
