# ADR-0001: 采用 Python Runtime + Java Gateway + Go 加速服务的多语言拓扑

- 状态：Accepted（重申于 2026-09-19 内核重构）
- 日期：2026-03（初始）/ 2026-09（复核）

## 背景

智能体编排生态（LangGraph/MCP 工具生态）在 Python 最成熟；企业 API 治理
（Spring Security/OAuth2 资源服务器、断言映射）在 Java 生态最完备；高并发
纯计算（评分/扇出/缓存）在 Go 下内存与延迟最优。单语言实现任一环节都要
妥协。

## 决策

保留三语言分工：`travel-agent-runtime`（Python，编排与智能）、
`travel-gateway`（Java，接入与策略）、4 个 Go 服务（ranker/fanout/
registry-cache/policy）。服务间契约以 `data-contracts/grpc/v1` proto +
`policy-core.v1.json` 为准，配 `scripts/check_grpc_stub_drift.py` 与
`scripts/check_policy_consistency.py` CI 门禁防漂移。

## 后果

- 正面：各环节使用最适配生态；契约先行使三端可独立演进。
- 负面：三套构建/测试/部署链（CI 已补 gofmt/vet/test、ruff、mvn test）；
  契约漂移依赖门禁而非编译器，必须保持 CI 红线。
