# gRPC 迁移计划（中文）

版本：2026-03-30

## 1. 范围

仅覆盖内部高频链路：

- Gateway -> Runtime
- Runtime -> Go Ranker
- Runtime -> Go Policy

对外接口保持 HTTP/JSON。

## 2. 目标

- 降低内部调用 p95
- 提升高并发吞吐
- 迁移过程中兼容旧链路

## 3. 分阶段执行

| 阶段 | 动作 | 成功标准 |
| --- | --- | --- |
| 0 | 定义 proto | 字段与 API 对齐并评审 |
| 1 | 双栈服务 | Runtime/Go 同时支持 HTTP+gRPC |
| 2 | Shadow 校验 | 比较 gRPC 与 HTTP 输出 |
| 3 | Canary 灰度 | 5%-10% 流量切换 |
| 4 | 全量切换 | 内部 HTTP 退役 |

## 4. Proto 合约（建议）

- `travel.runtime.RecommendRequest`
- `travel.runtime.RecommendResponse`
- `travel.policy.EvaluateRequest`
- `travel.policy.EvaluateResponse`
- `travel.ranker.ScoreRequest`
- `travel.ranker.ScoreResponse`

已落地的 v1 合约：

- `data-contracts/grpc/v1/common.proto`
- `data-contracts/grpc/v1/runtime.proto`
- `data-contracts/grpc/v1/policy.proto`
- `data-contracts/grpc/v1/ranker.proto`

## 5. 兼容性映射

- 字段名与 JSON key 保持一致
- Trace/Idempotency 通过 gRPC metadata 传递

## 6. 可观测性

- gRPC interceptor 注入 trace/audit
- Prometheus gRPC 指标（latency/errors）

## 7. 风险与缓解

| 风险 | 缓解 |
| --- | --- |
| 结果不一致 | Shadow 比对 + 差异阈值 |
| 客户端兼容 | 双栈 + 渐进切换 |
| 工具复杂度 | 统一 proto + codegen |

## 8. 工具链

- Python: `grpcio-tools`
- Go: `protoc-gen-go`, `protoc-gen-go-grpc`
- Java: `protobuf-maven-plugin` + `protoc-gen-grpc-java`（gateway）
- 可选：gRPC 反射

生成命令：

```powershell
python scripts/generate_grpc_stubs.py
Push-Location services/techgroup-enterprise-travel-gateway
mvn generate-sources
Pop-Location
```

