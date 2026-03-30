# gRPC Migration Plan (English)

Version: 2026-03-30

## 1. Scope

Internal hot paths only:

- Gateway -> Runtime
- Runtime -> Go Ranker
- Runtime -> Go Policy

Public endpoints remain HTTP/JSON.

## 2. Goals

- Reduce p95 latency on internal calls
- Improve throughput under burst loads
- Keep backward compatibility during migration

## 3. Phased Rollout

| Phase | Action | Success Criteria |
| --- | --- | --- |
| 0 | Define proto contracts | Reviewed API IDs and fields |
| 1 | Dual stack server | HTTP + gRPC in Runtime/Go services |
| 2 | Shadow calls | gRPC results compared with HTTP |
| 3 | Canary traffic | 5%-10% traffic to gRPC |
| 4 | Full cutover | HTTP disabled for internal hops |

## 4. Proto Contracts (Suggested)

- `travel.runtime.RecommendRequest`
- `travel.runtime.RecommendResponse`
- `travel.policy.EvaluateRequest`
- `travel.policy.EvaluateResponse`
- `travel.ranker.ScoreRequest`
- `travel.ranker.ScoreResponse`

## 5. Interop Mapping

- Keep field names aligned with existing JSON keys
- Preserve idempotency and trace headers via gRPC metadata

## 6. Observability

- gRPC server interceptors for trace/audit
- Prometheus gRPC metrics (latency, errors)

## 7. Risks & Mitigations

| Risk | Mitigation |
| --- | --- |
| Inconsistent results | Shadow compare + diff thresholds |
| Client compatibility | Dual stack, gradual cutover |
| Tooling complexity | Shared proto + codegen pipeline |

## 8. Tooling

- `grpcio-tools` for Python proto generation
- `protoc-gen-go` and `protoc-gen-go-grpc` for Go
- Optional: gRPC reflection for debugging

