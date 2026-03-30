# TechGroup Travel Recommendation API User Guide

## What This API Does

`POST /api/v1/travel/recommend` returns a complete travel recommendation package:

- hotel options
- transport options
- itinerary
- engagement recommendations
- AI explanation (`aiRationale`)

## Quick Request

```json
{
  "tenantId": "tenant-a",
  "userId": "u-01",
  "policyId": "policy-core.v1",
  "conversationId": "conv-01",
  "idempotencyKey": "idem-01",
  "city": "Hangzhou",
  "days": 2,
  "budget": 1800,
  "travelers": 1,
  "membershipTier": "silver",
  "preferences": ["lake", "food"],
  "maxAgentSteps": 6,
  "maxToolCalls": 12,
  "allowedTools": ["hotel.search", "transport.search", "attraction.search"]
}
```

## Quick Response

```json
{
  "traceId": "7e6f8f28-f731-4f40-a0a9-b95b84f6f31c",
  "aiRationale": "This plan balances budget and low transfer complexity.",
  "hotelOptions": [
    {
      "name": "West Lake Business Hotel",
      "score": 0.91
    }
  ],
  "transportOptions": [
    {
      "mode": "HSR",
      "cost": 320
    }
  ],
  "itinerary": [
    {
      "day": 1,
      "slots": ["West Lake", "Lingyin Temple"]
    }
  ],
  "engagementRecommendations": [],
  "auditLogs": [],
  "a2aLogs": []
}
```

## Notes

- Keep `idempotencyKey` unique for each real submission.
- Reusing the same `idempotencyKey` may be treated as replay by guard logic.
- `allowedTools` and `membershipTier` must satisfy policy checks.
- You can provide `X-Trace-Id` for easier end-to-end tracing.

## Common Errors

- `400 VALIDATION_ERROR`: request fields or value ranges are invalid.
- `403 POLICY_VIOLATION`: your current tier/tool/limit combination is denied by policy.
- `503 DEPENDENCY_UNAVAILABLE`: temporary runtime/dependency instability.
- `500 INTERNAL_ERROR`: unexpected platform fault.

Error payload format:

```json
{
  "code": "POLICY_VIOLATION",
  "message": "allowedTools contains unsupported tool",
  "traceId": "demo-trace-001",
  "path": "/api/v1/travel/recommend",
  "timestamp": 1774785600000,
  "suggestion": "Adjust membership tier, allowedTools, or policy limits"
}
```

## cURL Example

```bash
curl -X POST "http://localhost:8080/api/v1/travel/recommend" \
  -H "Content-Type: application/json" \
  -H "X-Trace-Id: demo-trace-001" \
  -d '{
    "tenantId": "tenant-a",
    "userId": "u-01",
    "policyId": "policy-core.v1",
    "conversationId": "conv-01",
    "idempotencyKey": "idem-01",
    "city": "Hangzhou",
    "days": 2,
    "budget": 1800,
    "travelers": 1,
    "membershipTier": "silver",
    "preferences": ["lake", "food"],
    "maxAgentSteps": 6,
    "maxToolCalls": 12,
    "allowedTools": ["hotel.search", "transport.search", "attraction.search"]
  }'
```

