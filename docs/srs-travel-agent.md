# 企业差旅智能体（Enterprise Travel Agent）软件需求规格说明书

| 文档属性 | 内容 |
|---|---|
| 文档编号 | SRS-TA-2026-001 |
| 版本 | 1.0 |
| 编制日期 | 2026-09-19 |
| 编制规范 | GB/T 9385-2008《计算机软件需求规格说明规范》 |
| 文档状态 | 依据代码库当前实现（commit 时点 2026-09-19）归纳，所有需求条目均可追溯至真实代码与测试 |
| 配套文档 | `docs/traceability-matrix.md`（需求-设计-验证追溯矩阵） |

---

## 1 引言

### 1.1 目的

本文档定义"企业差旅智能体"（Enterprise Travel Agent，下称"本系统"）的软件需求，包括功能需求（FR）与非功能需求（NFR），用于：

1. 作为开发、测试、验收与运维各方对系统行为的统一基线；
2. 作为需求—设计—测试追溯（见 `docs/traceability-matrix.md`）的锚点；
3. 作为上线门禁（go-live gate）与容量规划的口径来源。

本文档的所有功能需求均**自代码实现归纳而得**（模块来源列见每条 FR），不包含未实现能力的承诺；各条验收标准与仓库内真实测试用例一致。

### 1.2 范围

**包含**：
- 网关服务（Java/Spring Boot）：对外 REST API、策略校验、OIDC 资源服务器、内部 HMAC 签名、审计镜像；
- 运行时服务（Python/FastAPI）：多 Agent 编排、A2A 智能体间协作、MCP 工具调用与预算执行、会员分级准入、记忆后端、行程计划 DDD 聚合与持久化、流量防护、OIDC 认证、gRPC 端点；
- 策略评估服务（Go/OPA Rego）：策略决策、决策日志脱敏与签名；
- 评分服务（Go）：酒店/交通打分（HTTP + gRPC）；
- Web 前端（React）：登录令牌管理与路由保护；
- 部署基线（K8s manifests、GitOps、HPA/PDB）与 CI 门禁。

**不包含**：
- 真实支付、真实订单履约与票务出票（当前为推荐与规划域，不涉及交易执行）；
- 10B 用户 / 10M 并发的**实测**验证（相关内容仅为容量规划目标，见 NFR-004 口径说明）；
- 移动端小程序的详细交互规格（仓库含 `miniapp-wechat/` 结构校验，但本 SRS 不展开）。

### 1.3 术语与缩略语

| 术语 | 定义 |
|---|---|
| A2A | Agent-to-Agent，智能体间消息协作协议（本系统内为消息路由 + 回复闭环） |
| MCP | Model Context Protocol 风格的工具注册/调用层（本系统实现为带审计的进程内工具注册表） |
| OIDC | OpenID Connect，基于 Keycloak 的 JWT（RS256/JWKS）认证 |
| HMAC | Hash-based Message Authentication Code，服务间内部请求签名（HMAC-SHA256） |
| MoSCoW | Must / Should / Could / Won't 优先级分级法 |
| SLO | Service Level Objective，服务级目标 |
| DDD | Domain-Driven Design，领域驱动设计（聚合根、值对象、仓储端口） |
| fail-closed | 依赖失效时拒绝服务而非放行（与本系统的幂等语义相关） |
| 金丝雀（canary） | 按请求哈希将部分流量导至新后端并对比指标的发布方式 |
| 影子（shadow） | 用备用引擎并行计算但只记录对比事件、不影响主结果的观测方式 |
| Runtime | Python 运行时服务 `techgroup-enterprise-travel-runtime` |
| Gateway | Java 网关服务 `techgroup-enterprise-travel-gateway` |
| go-policy | Go 策略服务 `techgroup-enterprise-travel-policy-go` |
| go-ranker | Go 评分服务 `techgroup-enterprise-travel-ranker-go` |

### 1.4 参考标准

| 标准 | 名称与用途 |
|---|---|
| GB/T 9385-2008 | 《计算机软件需求规格说明规范》——本文档结构与条目化风格依据 |
| GB/T 8566-2022 | 《系统与软件工程 软件生存周期过程》——需求获取/验证/维护过程依据 |
| GB/T 25000.51-2016（ISO/IEC 25000 系列） | 系统与软件质量模型（功能适合性、性能效率、可靠性、安全性、可维护性、可移植性）——NFR 分类依据 |
| GB/T 22239-2019 | 网络安全等级保护基本要求——K8s 安全基线与认证要求的参考口径 |

---

## 2 总体描述

### 2.1 产品愿景

面向企业员工的差旅智能体：员工以城市、天数、预算、人数、偏好发起请求，系统在受控预算（Agent 步数/工具调用数）与分级策略（会员等级决定可用工具与编排引擎）约束下，通过多 Agent 协作产出"酒店 + 交通 + 每日行程 + 增值推荐（美食/活动/忠诚度/天气风险/增值销售/签证/礼宾/本地生活）"的完整差旅方案；平台侧通过网关策略校验、内部信任链（OIDC + HMAC）、幂等/限流/熔断与全链路审计保证企业级可运营性。

### 2.2 用户角色

| 角色 | 描述 | 关键诉求与对应能力 |
|---|---|---|
| 旅行者（企业员工） | 通过 Web 前端或客户端调用推荐 API 的最终用户 | 快速获得个性化推荐；会话记忆延续上下文（FR-020/021）；请求幂等防重复提交（FR-025） |
| 企业管理员 | 管理租户内成员与策略的运营人员 | 租户/用户/会话三段式作用域（FR-016）；会员分级控制工具与引擎准入（FR-009/010/012）；策略上限集中配置（FR-011，`policy-core.v1.json`） |
| 平台运维 | 负责部署、容量、观测与故障处置 | 健康检查（FR-026）；限流/熔断/并发上限（FR-025）；审计日志与决策日志脱敏签名（FR-007/013）；金丝雀/影子发布观测（FR-004/012）；CI 门禁与覆盖率（NFR-006） |

### 2.3 运行环境

**部署形态**：Kubernetes 集群（`platform/deploy/k8s/` 提供全量 manifests：deployment/service/hpa/pdb/networkpolicy/ingress/kustomize；GitOps 经 ArgoCD `platform/deploy/gitops/argocd-apps.yaml`）。已在本机 kind（Rancher Desktop）单节点集群完成功能链路验证与故障演练（证据：`stress/report_kind.json`、`docs/kind-loadtest-runbook.md` 第 5 节）。

**依赖中间件**（均为可选降级设计，缺失时系统可退化运行）：

| 中间件 | 用途 | 缺失时的行为（代码实证） |
|---|---|---|
| Redis（单机/Cluster） | 流量防护分布式计数、会话记忆、策略决策缓存、会员等级、A2A Streams 传输 | 降级为进程内本地限制并告警；`TRAVEL_GUARD_FAIL_CLOSED=true`（默认）时幂等声明拒绝（`traffic_guard.py`） |
| etcd / Nacos | Agent/工具服务注册发现（`discovery/`） | 本地注册表兜底（`local_fallback_registry.py`） |
| Pulsar | 事件总线、网关审计镜像 | 本地事件总线回退（`events/bus.py`，测试 `test_default_pulsar_falls_back_to_local_when_dependency_missing`） |
| Keycloak | OIDC 身份提供方（JWKS/RS256） | `TRAVEL_AUTH_MODE` 可设 internal/none（仅限本地开发，上线门禁禁止 none） |
| RocksDB / Milvus（或 faiss）/ SQLAlchemy | 可选记忆/持久化后端 | 缺依赖显式报错或回退（`memory/rocksdb_store.py`、`memory/vector_store.py`、`infrastructure/repositories.py`） |

**技术栈**：Python 3.12+ / FastAPI / LangGraph（可选）；Java 17 / Spring Boot 3 / Spring Security OAuth2；Go 1.x / Gin / OPA rego；前端 React + Vite。

### 2.4 设计与实现约束

1. HTTP 与 gRPC 必须复用同一应用函数（`runtime_recommend`），保证两条通道校验/预算/策略一致（`grpc/runtime_server.py` 模块注释与实现）。
2. 策略核心（会员→工具/引擎映射、步数/调用上限 50/30）必须在 Python、Java、Go 三处与 `data-contracts/policy-core/policy-core.v1.json` 保持一致（`scripts/check_policy_consistency.py`、`tests/test_policy_core_parity.py`）。
3. 写模型（行程计划持久化）故障不得阻断读路径（推荐响应），只记录告警（`application/recommend_service.py`）。
4. 上线门禁（`platform/deploy/scripts/go_live_final_check.py`）拒绝：staging/prod 使用 demo 共享密钥；prod 未启用 OIDC 或未配置语义 embeddings。
5. 决策日志输出必须对 userId/tenantId/conversationId/idempotencyKey 脱敏，并以 HMAC 签名防篡改（go-policy `main.go`）。

### 2.5 假设与依赖

- 假设 Keycloak realm 提供 `realm_access.roles` 或 `membershipTier` 声明用于等级映射（`api/auth.py::identity_from_claims`）。
- 假设网关与运行时共享 `TRAVEL_INTERNAL_SHARED_SECRET`（本地开发回退 demo 密钥并告警，staging/prod 由门禁拒绝）。
- 容量与性能指标（NFR-003/004）为规划目标：本机 kind 实测尚未达标，正式结论需在真实多节点集群重跑（`docs/kind-loadtest-runbook.md` 第 5.5 节）。

---

## 3 功能需求

> 约定：优先级采用 MoSCoW。"来源模块"为仓库内相对路径。"验收标准"采用 Given/When/Then，且与真实测试用例对应（测试证据详见追溯矩阵）。凡代码/测试未覆盖的行为，本文档不声称。

### 3.1 推荐主流程与编排

**FR-001 多章节旅行推荐主流程** — 优先级：Must
- 描述：给定城市、天数、预算、人数、偏好，系统返回包含酒店选项、交通选项、逐日行程与增值推荐四个章节的完整结果。
- 来源模块：`services/techgroup-enterprise-travel-runtime/src/travel_agent/orchestrator.py`（TravelOrchestrator.recommend）、`recommendation/recommender.py`、`models.py`
- 验收标准：
  - Given 请求 city=上海, days=2, budget=3200, travelers=1, preferences=[comfort]，When 调用 `recommend`，Then 结果包含 hotel_options、transport_options、itinerary、engagement_recommendations 四个非空章节；
  - Given 任一合法请求，When 推荐完成，Then 事件总线发布 `recommend.requested` 与 `recommend.completed` 事件（含各章节数量与引擎名）。

**FR-002 偏好技能权重个性化排序** — 优先级：Must
- 描述：系统按用户偏好加载技能权重（`skills/` 目录），并将权重乘入酒店/交通打分，使不同偏好产生不同排序。
- 来源模块：`skills/loader.py`（SkillLoader.load）、`recommendation/scoring.py`（tagMultiplier）
- 验收标准：
  - Given 两组不同偏好的同参数请求，When 分别推荐，Then 酒店选项排序随偏好权重变化；
  - Given 含权重标签的候选，When 打分，Then 得分为价格/质量因子与命中标签权重连乘之积。

**FR-003 多 Agent 协作编排** — 优先级：Must
- 描述：系统注册 11 个 Agent（manager/route-making/trip-planner/food-recommendation/local-event/local-lifestyle/loyalty-growth/weather-risk/ancillary-revenue/visa-compliance/concierge），由 ManagerAgent 按路线→行程→增值管线聚合各 Agent 产出。
- 来源模块：`agents/manager_agent.py`、`orchestrator.py::_register_agents`、`orchestration/engine.py`
- 验收标准：
  - Given 编排器初始化完成，When 查询注册中心，Then 11 个 agent 全部注册（含 visa-compliance-agent、concierge-agent、local-lifestyle-agent）；
  - Given local-life 与 culture 偏好请求，When 推荐，Then 增值推荐含 activity 与 souvenir 类型条目；
  - Given 引擎配置为 langgraph/agentscope/oneagents，When 运行，Then 发布 `recommend.engine_selected` 事件；Given 本地适配模式（local/native），When 运行，Then 回退为 langgraph。

**FR-004 编排引擎影子对比** — 优先级：Should
- 描述：配置 `TRAVEL_ORCHESTRATION_SHADOW_ENGINE` 后，系统在主引擎结果之外用影子引擎并行计算一次，并发布 `recommend.engine_shadow_compared` 对比事件（含两引擎增值推荐数量与适配器元数据）；影子失败发布 `recommend.engine_shadow_failed` 且不影响主结果。
- 来源模块：`orchestrator.py::_emit_shadow_engine_observation`、`orchestration/engine.py::build_engine_by_name`
- 验收标准：Given 影子引擎与主引擎不同，When 推荐，Then 事件流中出现 shadow_compared 事件；Given 影子引擎与主引擎相同（或为空/native），When 推荐，Then 不发布对比事件。

**FR-005 A2A 请求/回复闭环** — 优先级：Must
- 描述：编排器向 route-making-agent 与 trip-planner-agent 发布 A2A 任务；A2AWorker 消费接收方收件箱、执行已注册处理器（route_plan/trip_plan），并向发起方回投 `{topic}.reply` 消息（携带 correlation_id）；回复记录进入有界 A2A 日志（`direction=reply`）。
- 来源模块：`a2a/router.py`（A2ARouter）、`a2a/worker.py`（A2AWorker.drain）、`orchestrator.py::_register_a2a_handlers/_process_a2a_replies`
- 验收标准：
  - Given 一次推荐，When A2A 调度完成，Then a2a_logs 至少含 4 条（2 派发 + 2 回复）且存在 direction=reply 的记录；
  - Given A2A 派发异常，When 捕获，Then 发布 `recommend.a2a_dispatch_failed` 事件且推荐主流程继续。

**FR-006 A2A 传输可插拔与有界日志** — 优先级：Should
- 描述：A2A 传输层可插拔：默认进程内传输；配置 Redis Streams 传输后消息经 Streams 发布/消费；A2A 日志条数受 `TRAVEL_A2A_LOG_MAX_RECORDS`（默认 200）约束。
- 来源模块：`a2a/router.py`（RedisA2ATransport）、`orchestrator.py`（_bounded_append）
- 验收标准：Given Redis Streams 传输，When 发送并消费，Then 接收方收件箱返回原消息（correlation_id 保持）；Given 超过上限的日志写入，When 追加，Then 日志长度不超过上限且保留最新记录。

**FR-025 A2A HTTP 查询端点** — 优先级：Should
- 描述：Runtime 暴露 `POST /a2a/send` 与 `GET /a2a/inbox/{receiver}`；OIDC 模式下两个端点均要求 Bearer 令牌。
- 来源模块：`api/app.py::a2a_send_endpoint/a2a_inbox_endpoint`
- 验收标准：Given sender/receiver/topic/payload，When POST /a2a/send，Then 返回 message（含 id/sender/receiver/topic/payload/timestamp/correlation_id）；When GET inbox，Then 返回该接收方消息列表；OIDC 模式下无有效令牌则拒绝。

### 3.2 MCP 工具与预算执行

**FR-007 MCP 工具注册与调用审计** — 优先级：Must
- 描述：系统注册 7 个数据检索工具（search_hotels/search_transports/search_attractions/search_foods/search_events/search_activities/search_souvenirs），每次调用记录审计日志（工具名、入参、上下文、耗时 latency_ms、结果数），审计日志条数受 `TRAVEL_MCP_AUDIT_MAX_RECORDS`（默认 500）约束；工具同时登记至服务发现中心。
- 来源模块：`mcp/registry.py`（MCPToolRegistry）、`orchestrator.py::_register_tools`
- 验收标准：Given 一次推荐，When 检查 registry.audit_logs，Then 至少包含 search_hotels/search_transports/search_attractions 的调用记录且每条含 latency_ms；Given 未注册工具名，When 调用，Then 抛出"Tool not found"错误。

**FR-008 Agent 步骤与工具调用预算执行** — 优先级：Must
- 描述：每请求可设 ExecutionBudget（maxAgentSteps/maxToolCalls），在执行期强制：MCP 注册表每次工具调用消耗一个工具调用额度，编排引擎每个管线阶段消耗一个步骤额度；超限抛出 BudgetExceeded（上游表现为 4xx 类失败）；预算快照经 `recommend.budget_snapshot` 事件发布。
- 来源模块：`orchestration/budget.py`（ExecutionBudget/BudgetExceeded/ContextVar）、`mcp/registry.py`、`orchestration/engine.py`
- 验收标准：
  - Given maxToolCalls 耗尽，When 再次调用工具，Then 抛出 BudgetExceeded 且消息含已用/上限；
  - Given maxAgentSteps 耗尽，When 进入下一管线阶段，Then 抛出 BudgetExceeded；
  - Given 充足预算，When 完整推荐，Then 正常完成且 snapshot 记录 used_agent_steps/used_tool_calls。

### 3.3 会员分级与准入

**FR-009 会员分级工具准入** — 优先级：Must
- 描述：按会员等级过滤 allowedTools：basic{hotels,transports,attractions}、silver(+foods,activities)、gold/platinum(+events,souvenirs)；未在等级工具集内的请求工具被剔除或拒绝。策略可由 `policy-core.v1.json` 覆盖（`TRAVEL_POLICY_CORE_FILE`）。
- 来源模块：`access/control.py`（enforce_tools_for_tier/_DEFAULT_TIER_POLICIES/_load_policy_core）
- 验收标准：
  - Given basic 等级请求含 search_foods，When 过滤，Then search_foods 被剔除；
  - Given gold 等级请求含 search_events，When 过滤，Then 保留；
  - Given 未知等级，When 查询策略，Then 回退 basic。

**FR-010 会员分级引擎准入与运行时策略评估** — 优先级：Must
- 描述：运行时按策略评估（evaluate_policy）：maxAgentSteps≤50、maxToolCalls≤30、allowedTools ⊆ 等级工具集、编排引擎 ∈ 等级引擎集（basic 仅 langgraph，silver +agentscope，gold/platinum +oneagents；含别名归一 agentscope-ai/oneagent/native）；不满足则拒绝请求并返回原因。
- 来源模块：`access/control.py::evaluate_policy`、`api/app.py::runtime_recommend`
- 验收标准：Given 等级 basic 且引擎为 agentscope（经配置），When runtime_recommend，Then 拒绝并返回 "membershipTier cannot use current orchestration engine"；Given maxAgentSteps=51，When 评估，Then 拒绝并返回 "maxAgentSteps exceeds policy limit"。

**FR-011 策略核心三方一致性与金标准用例** — 优先级：Must
- 描述：策略核心（等级→工具/引擎映射、上限、别名）以 `data-contracts/policy-core/policy-core.v1.json` 为唯一事实源，Python、Java、Go 三处实现一致，并有金标准用例集；CI 脚本校验一致性。
- 来源模块：`data-contracts/policy-core/policy-core.v1.json`、`data-contracts/policy-core/cases/golden_cases.v1.json`、`scripts/check_policy_consistency.py`
- 验收标准：Given 金标准用例集，When 逐一评估，Then 三方实现判定一致（allow/deny 与 reason 相同）。

**FR-012 Gateway 策略校验（本地/Go 后端、金丝雀分流、影子对比、双级缓存）** — 优先级：Must
- 描述：网关在转发前本地评估策略（PolicyCoreSpec）；配置 `TRAVEL_POLICY_BACKEND=go` 时调 Go 策略服务 `/v1/policy/evaluate`；`canary` 模式按 SHA-256(租户:用户:幂等键) 取模百分比分流；`TRAVEL_POLICY_SHADOW=true` 时并行跑本地策略并打印分歧；决策缓存两级（进程内 + 可选 Redis，TTL 默认 3s）；`GET /policy/cache/stats` 暴露命中统计。
- 来源模块：`services/techgroup-enterprise-travel-gateway/src/main/java/com/techgroup/travel/gateway/service/PolicyGuardService.java`
- 验收标准：
  - Given 请求含等级不支持的 allowedTools，When validate，Then 抛出 IllegalArgumentException（POLICY_VIOLATION）；
  - Given backend=go 且 Go 返回 deny，When validate，Then 抛出异常（reason 透传）；
  - Given backend=go 且重复请求，When 第二次 validate，Then 命中进程内缓存（cacheHits 增加，不再调用 Go）；
  - Given Redis 缓存已存决策，When validate，Then 优先读取 Redis 决策；
  - Given canary percent=0，When shouldUseGo，Then 恒否。

**FR-013 Go 策略评估服务（Rego、决策日志脱敏与签名）** — 优先级：Must
- 描述：go-policy 以 OPA Rego（`policy.rego`）评估 allow/reason：上限 50/30、等级工具/引擎集与别名归一；评估结果带进程内缓存（默认 TTL 5s）；每次决策异步投递决策日志（日志对 userId/tenantId/conversationId/idempotencyKey 脱敏；配置 `GO_POLICY_DECISION_LOG_SIGNING_KEY` 时附 HMAC-SHA256 签名；队列满时直接落盘打印）；请求体 DisallowUnknownFields；提供 `GET /health`。
- 来源模块：`services/techgroup-enterprise-travel-policy-go/main.go`、`policy.rego`、`policy_core.go`
- 验收标准：
  - Given maxAgentSteps≤50 且工具/引擎合规，When evaluate，Then decision=allow, reason=ok；
  - Given 超限/越权工具/引擎与等级不匹配，When evaluate，Then decision=deny 且 reason 为对应文案；
  - Given 请求含未知字段，When 绑定，Then 返回 400。

**FR-014 会员等级存取** — 优先级：Should
- 描述：MembershipStore 按 (tenant, user) 存取等级；配置 Redis（含 Cluster 模式）时持久化（TTL 默认 30 天），否则内存表；Runtime 在请求未显式携带 membershipTier 时以此补齐（默认 basic）。
- 来源模块：`membership_store.py`、`api/app.py`
- 验收标准：Given set_tier("t","u","gold")，When get_tier，Then 返回 gold；Given 未设置，When get_tier，Then 返回 None（上游回退 basic）。

### 3.4 对外 API 与信任链

**FR-015 Gateway 推荐 API（校验、编排转发、审计镜像、AI 建议）** — 优先级：Must
- 描述：`POST /api/v1/travel/recommend`：请求体校验（tenantId/userId/policyId/conversationId/idempotencyKey/city 必填，days/budget/travelers≥1，allowedTools 非空）→ 策略校验（FR-012）→ 调用 Runtime（FR-019 头部）→ 异步镜像审计至 Pulsar（可选开关）→ 生成 AI rationale（Spring AI 不可用时回退模板文案）→ 返回 traceId、rationale、hotel_options、transport_options、itinerary、engagement_recommendations、audit_logs、a2a_logs。校验失败返回 400 VALIDATION_ERROR，策略拒绝返回 403 POLICY_VIOLATION。
- 来源模块：`api/TravelGatewayController.java`、`api/GlobalExceptionHandler.java`、`api/dto/TravelRecommendRequest.java`、`service/PulsarAuditMirrorService.java`、`service/SpringAiAlibabaAdvisorService.java`
- 验收标准：
  - Given 合法请求与 mock Runtime，When POST /recommend，Then 200 且响应含上述字段；
  - Given allowedTools 引用未支持工具，When POST，Then 403 且 error 契约为 POLICY_VIOLATION；
  - Given 缺失必填字段，When POST，Then 400 且 error 契约为 VALIDATION_ERROR。

**FR-016 Runtime 受控推荐 API（内部信任链 + 会话域 + 全量防护）** — 优先级：Must
- 描述：`POST /runtime/recommend` 依序执行：X-Trace-Id 必填 → 内部客户端白名单（X-Internal-Client-Id）→ HMAC 签名校验（FR-019）→ tenant/user/conversation 会话域必填 → 限流 → 幂等声明 → 熔断放行 → 并发上限（inflight）→ 读取会话记忆快照 → 等级解析与工具过滤/策略评估（FR-009/010）→ 预算内执行（FR-008）→ 行程计划落库（FR-022，失败不阻断）→ 返回 trace_id、memory_before/after/hits、四章节结果、audit_logs、a2a_logs、注册的 agents/tools。
- 来源模块：`api/app.py::runtime_recommend`
- 验收标准：
  - Given 缺失 X-Trace-Id，When 调用，Then 报错 "missing X-Trace-Id"；
  - Given 正确的内部头与签名，When 调用，Then 成功返回含 memory 快照与审计日志的完整响应；
  - Given 缺失 tenantId/userId/conversationId 之一，When 调用，Then 报错 "missing conversation scope"；
  - Given 重复 idempotencyKey，When 二次调用，Then 报错 "duplicate submission"；
  - OIDC 模式下，Given 合法 Bearer 令牌，When 调用，Then 身份声明并入请求上下文（HMAC 仍然强制）。

**FR-017 Runtime OIDC 认证与身份映射** — 优先级：Must
- 描述：`TRAVEL_AUTH_MODE=oidc` 时，Runtime 验证 Authorization: Bearer JWT：仅接受 RS256；校验 iss/aud/exp/nbf；按 kid 从 Keycloak JWKS（缓存 TTL 默认 300s，可强制刷新）选钥验签，验签失败且疑似换钥时刷新一次重试；从 claims 映射身份（sub→userId、tenant_id/tenantId→tenantId、realm_access.roles 或 membershipTier→membershipTier，缺 sub 拒绝）。`internal` 模式仅 HMAC（本地开发/兼容）；`none` 为显式无认证模式（上线门禁禁止）。
- 来源模块：`api/auth.py`（OidcAuthenticator/verify_token/identity_from_claims/auth_mode）
- 验收标准：
  - Given 本地 RSA 签发的合法令牌，When authenticate，Then 返回 claims 且身份映射正确（多等级角色时取最强等级）；
  - Given 过期/错误 aud/错误 iss/alg=none/垃圾串令牌，When authenticate，Then 分别拒绝（expired/audience mismatch/issuer mismatch/unsupported alg/malformed）；
  - Given TRAVEL_AUTH_MODE 环境变量，When auth_mode，Then 仅接受 oidc/internal/none，其余回退 internal。

**FR-018 Gateway OIDC 资源服务器** — 优先级：Must
- 描述：`travel.security.mode=oauth2` 时，Gateway 安装 JWT 资源服务器过滤链（JwtDecoders.fromIssuerLocation），放行 `/api/v1/travel/health`、`/actuator/health`、`/actuator/info`，其余请求必须认证；mode=off（或缺省）时安装 permit-all 回退链并告警（仅限本地开发/测试，上线门禁在 staging/prod 拒绝）。
- 来源模块：`config/SecurityConfig.java`、`platform/deploy/scripts/go_live_final_check.py`
- 验收标准：
  - Given mode=oauth2 与 issuer-uri，When 请求受保护路径且无令牌，Then 401（过滤器链行为）；
  - Given staging/prod 环境模板含 demo 密钥或 prod 未启用 OIDC，When 运行上线门禁，Then 门禁失败（自动化：`tests/test_go_live_final_check.py::test_security_env_gate_staging_rejects_demo_secret`、`test_security_env_gate_prod_requires_oidc_and_semantic_embeddings`）；
  - 过滤链本身的 HTTP 层行为当前**无自动化测试**，验收依赖人工/环境验证（见追溯矩阵）。

**FR-019 内部 HMAC 服务间签名** — 优先级：Must
- 描述：Gateway 以 HMAC-SHA256 对 "{idempotencyKey}.{clientId}" 签名（共享密钥为 MAC key），经 `X-Internal-Client-Id`/`X-Internal-Signature` 头传递；Runtime 以恒定时间比较（hmac.compare_digest）验证，clientId 必须与白名单一致，防止签名跨调用者重放。双端实现逐字对齐（Python `make_internal_signature` ↔ Java `InternalTokenService.sign`）。
- 来源模块：`security.py`、`api/app.py::_verify_signature`、`service/InternalTokenService.java`、`service/PythonRuntimeClient.java`
- 验收标准：
  - Given Gateway 构造请求，When 检查出站头，Then 含 X-Trace-Id、traceparent、X-Internal-Client-Id、X-Internal-Signature 四头；
  - Given 正确签名与白名单 clientId，When Runtime 校验，Then 通过；
  - Given 空签名/被篡改签名/非白名单 clientId，When 校验，Then 失败（"invalid internal signature"/"untrusted internal client"）。

### 3.5 记忆与持久化

**FR-020 对话记忆多后端** — 优先级：Must
- 描述：`TRAVEL_MEMORY_BACKEND` 支持四后端：memory（进程内，默认）、redis（支持 Cluster 模式，TTL 默认 86400s）、rocksdb（要求 `TRAVEL_ROCKSDB_PATH` 与 rocksdb 包，缺一则显式报错）、vector（Milvus/faiss/本地词面回退；memory_key 限安全字符集防注入）。每次受控推荐前后向 memory_key（tenant:user:conversation）写入请求与结果序列化记录。
- 来源模块：`memory/base.py`、`memory/in_memory.py`、`memory/redis_store.py`、`memory/rocksdb_store.py`、`memory/vector_store.py`、`orchestrator.py::_build_memory_store/_run_with_memory`
- 验收标准：
  - Given recommend_with_memory 调用，When 读回 memory_key，Then 至少含 request 与 recommendation 两条记录；
  - Given backend=redis 且 Redis Cluster 配置，When 初始化，Then 以 RedisCluster 客户端接入；
  - Given backend=rocksdb 且缺路径/缺包，When 初始化，Then 显式 RuntimeError；
  - Given 未知 backend 值，When 初始化，Then RuntimeError（拒绝启动）。

**FR-021 记忆相似检索** — 优先级：Should
- 描述：`query_memory(key, query, limit)` 提供按内容相关度检索历史消息：vector 后端做词面相似打分排序；其余后端回退为最近 N 条读取；返回值并入 Runtime 响应的 memory_hits。
- 来源模块：`memory/base.py::query_messages`、`memory/vector_store.py`、`api/app.py`
- 验收标准：Given vector 后端写入多条含"北京"的历史，When query("北京")，Then 相关消息优先返回（limit=3）。

**FR-022 行程计划 DDD 聚合与持久化** — 优先级：Must
- 描述：领域层定义 TripPlan 聚合根（不变量：city 非空、days∈[1,30]、travelers≥1、Budget>0；confirm() 要求至少一条酒店与一条交通选项），发布领域事件（TripPlanOptionsAttached/TripPlanConfirmed）；仓储端口 TripPlanRepository 由 InMemory 与 SqlAlchemy 适配器实现（后者当前镜像至内存兜底，DB 中断不阻断读路径，受 `TRAVEL_PERSIST_TRIP_PLANS` 开关控制）。应用服务 `plan_trip` 将推荐结果映射为聚合并持久化。
- 来源模块：`domain/travel.py`、`application/recommend_service.py`、`infrastructure/repositories.py`
- 验收标准：
  - Given days=0 或 travelers=0 或 budget≤0，When 构造 TripPlan，Then ValueError（不变量拒绝）；
  - Given 无酒店选项的 plan，When confirm，Then ValueError；
  - Given 聚合 save 后 get/list_by_city，Then 往返一致（按城市倒序）；
  - Given plan_trip 传入推荐结果，Then 各章节映射至聚合且事件被记录。

### 3.6 评分与降级

**FR-023 Go Ranker 评分服务与降级回退** — 优先级：Must
- 描述：go-ranker 提供酒店打分（价格因子 min(1.4, budget/price)×0.45 + 质量因子 rating/5×0.55，乘标签权重连乘）与交通打分（价格因子 min(1.5, budget/price)×0.55 + 速度因子 1/max(duration,0.5)×0.45），HTTP `/v1/score/hotel|transport`（含 /batch）与 gRPC `RankerService.ScoreHotel/ScoreTransport`（默认 9090）双通道，得分保留 8 位小数。Python 侧 GoRankerClient：未配置后端返回 None（用本地打分）；Go 后端失败回退 None；gRPC 传输失败回退 HTTP；金丝雀批量部分成功时返回稀疏结果。请求体 DisallowUnknownFields。
- 来源模块：`services/techgroup-enterprise-travel-ranker-go/main.go`、`recommendation/go_ranker_client.py`
- 验收标准：
  - Given 高评分低价候选，When hotelScore，Then 排序靠前（质量与价格双因子生效）；Given price=0，When 打分，Then 不 panic；
  - Given 批量与单次打分，When 比较，Then 结果一致；
  - Given Go 后端不可达，When 打分，Then 回退 None（本地打分接管）；Given gRPC 失败，When 重试，Then 回退 HTTP。

### 3.7 gRPC 与健康

**FR-024 Runtime gRPC 端点** — 优先级：Should
- 描述：`TRAVEL_RUNTIME_GRPC_ENABLED=true` 时启动 gRPC `RuntimeService.Recommend`（默认端口 9092），复用与 HTTP 完全相同的 `runtime_recommend` 应用函数（同一校验/预算/策略）；契约违反映射为 gRPC InvalidArgument；附 `GET /health/grpc`。
- 来源模块：`grpc/runtime_server.py`、`data-contracts/grpc/v1/runtime.proto`、`api/app.py`
- 验收标准：Given 合法 RuntimeRecommendRequest（含必需头字段），When gRPC Recommend，Then 返回与 HTTP 同构的响应（trace_id/四章节/memory/审计）；Given 缺会话域请求，When 调用，Then InvalidArgument。

**FR-026 健康检查端点** — 优先级：Must
- 描述：各服务提供健康探针端点：Runtime `GET /health`（及 gRPC 启用时 `/health/grpc`）、Gateway `GET /api/v1/travel/health`、go-policy `GET /health`、go-ranker `GET /health`；K8s readiness/liveness 探针引用（`platform/deploy/k8s/deployment.yaml`）。
- 来源模块：`api/app.py`、`api/TravelGatewayController.java::health`、go 两个 main.go
- 验收标准：Given 服务存活，When GET 对应 /health，Then 200 且 body 为 {"status":"ok"}（或含 grpc_port）。**当前无针对 /health 的自动化测试**，验收为人工/探针验证（见追溯矩阵）。

### 3.8 流量防护与事件

**FR-027（原 3.8 首条，编号调整说明见下）流量防护四件套（限流/幂等/熔断/并发上限）** — 优先级：Must

> 注：为保持编号连续性，本 FR 采用 FR-027 编号，追溯矩阵同名对应。

- 描述：TrafficGuard 提供分布式（Redis/Cluster）与进程内两级实现：
  - 限流：按 scope 计数，窗口/上限由 `TRAVEL_RATE_LIMIT_PER_MINUTE`（默认 200）/`TRAVEL_RATE_LIMIT_WINDOW_SEC`（默认 60）控制；
  - 幂等：`SET NX EX`（TTL 默认 900s）实现 at-most-once；Redis 配置过但出错（degraded）且 `TRAVEL_GUARD_FAIL_CLOSED=true`（默认）时拒绝声明，防重复扣减；
  - 熔断：连续失败阈值（默认 5）触发开启，冷却期（默认 30s）后半开仅放行有限探测（默认 1），成功清零；
  - 并发上限：inflight 计数 + TTL（默认 2000/30s），完成后释放。
  - Redis 缺失时使用进程内限制（设计内单机模式）；Redis 运行时故障降级并告警（degraded 指标可暴露）。
- 来源模块：`traffic_guard.py`
- 验收标准：
  - Given 同一 (tenant, idemKey) 两次声明，Then 第二次拒绝（duplicate submission）；
  - Given 环境变量调整限流阈值，Then 生效（env 测试）；
  - Given 连续失败达阈值，When allow_circuit，Then 拒绝；Given 冷却期过后首次请求，Then 放行探测；Given 成功，Then 熔断清零；
  - Given 本地 inflight 达上限，When claim，Then 拒绝；
  - Given Redis 配置但连接失败且 fail_closed=true，When claim_idempotency，Then 返回 False（fail-closed）。

**FR-028 事件总线与事件消费** — 优先级：Should
- 描述：事件总线可插拔（Pulsar/本地回退；strict 模式缺依赖显式报错）；本地总线保留事件供调试；事件消费者管线处理 audit/profile/notification 并带重试与 DLQ 指标；A2A 指标可导出（`TRAVEL_A2A_AUDIT_MIRROR_PULSAR` 等）。
- 来源模块：`events/bus.py`、`events/consumer.py`、`scripts/run_event_consumers.py`、`a2a` 指标导出脚本
- 验收标准：
  - Given 默认配置缺 Pulsar 依赖，When 构建总线，Then 回退本地（strict=false）；Given strict=true，Then 显式报错；
  - Given 本地事件流，When 运行消费者管线，Then 产出 audit/profile/notification 结果并记录重试/DLQ 指标。

**FR-029 Web 端令牌管理与路由保护** — 优先级：Must
- 描述：Web 前端以 localStorage 持久化 Bearer 令牌（TOKEN_KEY=travel_web_auth_token）：getToken/setToken（空值清除）/isAuthenticated 三个原语；受保护路由未认证时跳转登录页。
- 来源模块：`apps/techgroup-enterprise-travel-web/src/auth.ts`（近期由 auth.js 迁移至 TypeScript，行为不变）、`ProtectedRoute.tsx`、`LoginPage.tsx`
- 验收标准：
  - Given setToken("abc")，When getToken，Then 返回 "abc"；
  - Given setToken("")，When getToken，Then 返回空串（令牌被清除）；
  - Given 未设置令牌，When isAuthenticated，Then false。

> 编号说明：FR-025（A2A HTTP 端点）、FR-027（流量防护）的编号按主题分组排布，实际顺序以本文档条目为准；追溯矩阵与本节一一对应。

---

## 4 非功能需求

> 每条 NFR 含量化指标与验收方法。凡涉及"实测状态"的条目均注明当前证据，避免夸大。

**NFR-001 性能（API 延迟）** — 优先级：Must
- 指标口径（目标）：网关推荐 API p95 ≤ 300ms、p99 ≤ 700ms（来源：`docs/platform-product-spec.md` 第 5 节、`docs/global-active-active-deployment-plan.md`）。kind 演练门禁按 p95<1200ms/p99<1500ms 放行冒烟（`stress/k6_recommend.js`）。
- 当前实测状态（**必须如实说明**）：本机 kind 单节点、2 副本、50 并发 × 3000 请求实测：成功率 87.53%，平均 501ms，p95=1304.63ms，p99=1667.79ms（证据：`stress/report_kind.json`、`docs/kind-loadtest-runbook.md` 第 5.3 节）。**目标未达成**；签名演练报告 `stress/multi_region_fault_drill_report_kind.json` pass=false（门禁如实拒绝）。
- 验收方法：在真实多节点集群重跑 `platform/deploy/scripts/run_kind_loadtest.sh`（k6，`--environment staging`），以 `stress/ingest_schema_adapters.py` 采集格式入库并对照 SLO 门禁。

**NFR-002 可用性** — 优先级：Must
- 指标：月度可用性 ≥ 99.9%（对应月停机 ≤ 43.2 分钟）；故障自愈：Pod-Kill 后 rollout 恢复。
- 当前实测状态：kind 集群 3 轮 Pod-Kill 混沌演练全部通过，恢复合计 13 秒（`docs/kind-loadtest-runbook.md` 第 5.4 节）；99.9% 长期指标**未实测**，依赖生产 SLO 监控建立。
- 验收方法：生产监控（Prometheus/告警）月度报告；混沌演练脚本复跑。
- 支撑设计（代码实证）：无 Redis 降级不 fail-open、写模型故障不阻断读路径（FR-022）、Pulsar 缺失回退本地事件、go-ranker 失败回退本地打分（FR-023）、K8s PDB/HPA manifests。

**NFR-003 容量规划目标** — 优先级：Should
- 指标口径：**10 亿（10B）注册用户 / 1000 万（10M）并发**为架构容量规划目标（`docs/industrial-scale-upgrade-plan-10b-10m.md`），**非实测结论**——该文档明确声明"不能替代正式 10B/10M 生产主张所需的分布式证据"。
- 规划模型：容量/成本模型（`stress/capacity_cost_model.py`、`stress/capacity_cost_report.md`）以峰值在线 100 万、活跃比 0.1、网关单 Pod 1.2 万连接、Runtime 单 Pod 100 活跃、安全系数 1.8 估算出网关 150 Pod / Runtime 1800 Pod / 13 分区；报告自注"This is planning estimation, not production evidence"。
- 验收方法：分布式基准（`stress/distributed_benchmark_evidence.*`）+ 金丝雀对比报告 + 容量分区验证（`tests/test_capacity_partitioning.py`、`tests/test_capacity_cost_model.py` 为模型级单元验证）。

**NFR-004 安全性** — 优先级：Must
- 要求与现状：
  1. 端到端用户认证：OIDC（Keycloak，RS256/JWKS，iss/aud/exp 校验）——Runtime 与 Gateway 双侧实现并有自动化测试（FR-017/018）；
  2. 服务间信任：HMAC-SHA256 绑定 clientId + 恒定时间比较（FR-019）；
  3. fail-closed：幂等声明在降级态默认拒绝（FR-027）；
  4. 密钥治理：staging/prod 禁止 demo 密钥（上线门禁自动检查，FR-018 验收标准 2）；
  5. 决策日志脱敏 + HMAC 防篡改（FR-013）；
  6. K8s 基线：networkpolicy/serviceaccount/tls-secret manifests 在库（`platform/deploy/k8s/`）；CI 含 security-scan job（`.github/workflows/ci-cd.yml`）。
- 验收方法：单元测试（`tests/test_api_auth.py` 全套负例）、上线门禁（`tests/test_go_live_final_check.py`）、CI security-scan；K8s 基线合规性人工评审。
- 已知边界：Runtime 本地开发允许 demo 共享密钥回退（显式告警 + 门禁拦截 staging/prod）；Gateway mode=off 链仅限本地（同上）。Vector 记忆 memory_key 白名单防注入（`memory/vector_store.py`）。

**NFR-005 可靠性工程约束（幂等/降级语义）** — 优先级：Must
- 要求：重复提交必须被幂等层拦截（at-most-once）；任何中间件故障不得造成静默放行（fail-open）。
- 验收方法：`tests/test_membership_and_guard.py::test_traffic_guard_limit_and_idempotency`、`tests/test_api_contract.py::test_runtime_recommend_rejects_duplicate_submission`、`tests/test_traffic_guard_scale_controls.py`。

**NFR-006 可维护性** — 优先级：Must
- 要求与现状：
  1. Python 测试覆盖率门槛 **50%**（CI `coverage report --fail-under=50`，`.github/workflows/ci-cd.yml` python-tests job）；
  2. Lint 门禁：`ruff check`（services/tests/scripts/stress/platform）作为独立 CI job；
  3. Java `mvn -B test`、Go `go test ./...`、Web 安装-测试-构建均为 CI 必过 job；
  4. Python 测试当前 104 个（`grep -r "def test_" tests/ | wc -l`）。
- 验收方法：CI 流水线绿即为验收；覆盖率报告 `coverage-python.xml`。

**NFR-007 可观测性** — 优先级：Should
- 要求与现状：
  1. 全链路 trace：X-Trace-Id 贯穿 Gateway→Runtime；Gateway 注入 W3C traceparent（`PythonRuntimeClient.java`）；OTel 追踪可选启用（`TRAVEL_OTEL_ENABLED=true`，OTLP gRPC 导出，`observability/tracing.py`）；
  2. 指标：策略缓存命中统计 API（FR-012 `/policy/cache/stats`）；金丝雀门禁输出 Prometheus 指标（`platform/deploy/scripts/canary_gate.py`）；A2A 指标导出（`stress/a2a_metrics_export` 流程 + `tests/test_a2a_metrics_export.py`）；
  3. 事件/审计：MCP 审计日志、A2A 日志（有界）、Pulsar 审计镜像（FR-007/006/015）；gRPC 决策日志（脱敏+签名，FR-013）。
- 验收方法：单元测试（`test_go_live_final_check.py::test_parse_prom_metrics`、`test_canary_gate.py::test_load_prometheus_metrics`、`test_a2a_metrics_export.py::test_collect_and_write_metrics`）；OTel 实际导出链路为人工/环境验证（无集成测试）。

**NFR-008 可移植性** — 优先级：Must
- 要求：全部服务容器化并经 K8s 部署：CI 构建并推送 travel-web/travel-gateway/travel-runtime/go-ranker/go-policy/go-fanout/go-registry-cache 镜像（`.github/workflows/ci-cd.yml` docker job）；`platform/deploy/k8s/` 全量 manifests（deployment/hpa/pdb/service/ingress/kustomize/argocd）；已在 kind（Rancher Desktop）验证镜像构建→部署→压测→混沌全流程（`docs/kind-loadtest-runbook.md` 第 5 节，含三个构建级 bug 的修复记录）。
- 验收方法：CI 镜像构建成功 + kind 集群一键部署（`docs/kind-loadtest-runbook.md` 第 1 节）+ 部署后探针通过。

---

## 5 外部接口需求

### 5.1 Gateway REST API（对外）

`POST /api/v1/travel/recommend`（`TravelGatewayController`，契约 `api/dto/TravelRecommendRequest.java`）

请求体（必填校验 jakarta.validation）：

```json
{
  "tenantId": "string*", "userId": "string*", "policyId": "string*",
  "conversationId": "string*", "idempotencyKey": "string*",
  "city": "string*", "days": 3, "budget": 3000.0, "travelers": 1,
  "membershipTier": "basic|silver|gold|platinum",
  "preferences": ["comfort"], "maxAgentSteps": 10, "maxToolCalls": 10,
  "allowedTools": ["search_hotels", "search_transports", "search_attractions"]
}
```

响应 200（`TravelRecommendResponse`）：`traceId, aiRationale, hotel_options[], transport_options[], itinerary[], engagement_recommendations[], audit_logs[], a2a_logs[]`。
错误契约（`GlobalExceptionHandler`）：400 `VALIDATION_ERROR` / 403 `POLICY_VIOLATION` / 404 `NOT_FOUND`，body 含 code/message/timestamp/path/suggestion（`ApiError.java`）。

其它：`GET /api/v1/travel/health`（探针，免认证）、`GET /api/v1/travel/policy/cache/stats`（缓存命中指标）。

### 5.2 Runtime REST API（网关内部）

`POST /runtime/recommend`（`api/app.py::runtime_recommend_endpoint`）。请求头：`X-Trace-Id`（必填）、`X-Internal-Client-Id`（白名单）、`X-Internal-Signature`（HMAC-SHA256(idempotencyKey.clientId)）、`Authorization: Bearer`（oidc 模式）。请求体在 5.1 基础上由 Gateway 转发（`PythonRuntimeClient` 组装同名字段）。响应含 `trace_id, memory_before, memory_after, memory_hits, hotel_options, transport_options, itinerary, engagement_recommendations, audit_logs, a2a_logs, registered_agents, registered_tools`。

开发辅助端点：`POST /recommend`（无内部信任链的直连推荐，供本地调试）、`POST /a2a/send`、`GET /a2a/inbox/{receiver}`、`GET /health`、`GET /health/grpc`。

### 5.3 gRPC 契约（`data-contracts/grpc/v1/`）

| 服务 | RPC | 说明 |
|---|---|---|
| `RuntimeService`（runtime.proto） | `Recommend(RuntimeRecommendRequest) returns (RuntimeRecommendResponse)` | Python Runtime 提供（9092），复用 HTTP 应用函数；响应含 memory/audit/a2a/registered 字段 |
| `RankerService`（ranker.proto） | `ScoreHotel(ScoreRequest) returns (ScoreResponse)`；`ScoreTransport(...)` | go-ranker 提供（9090，keepalive 30s/10s）；ScoreRequest{price,rating,duration,tags,budget,weights} |
| `PolicyService`（policy.proto） | 契约已生成（`policy_pb2*`、Gateway 内 `policy.proto` stub） | 当前网关经 HTTP 调 go-policy `/v1/policy/evaluate`；gRPC 契约预留 |

### 5.4 go-policy HTTP 接口

`POST /v1/policy/evaluate`：请求体为 5.1 字段子集 + `orchestrationEngine`；响应 `{"decision":"allow|deny","reason":"..."}`；未知字段 400。决策日志异步 POST 至 `GO_POLICY_DECISION_LOG_ENDPOINT`（脱敏 + HMAC 签名）。

### 5.5 A2A 消息格式（`a2a/protocol.py`）

```json
{
  "id": "uuid", "sender": "manager-agent", "receiver": "route-making-agent",
  "topic": "route_plan", "payload": {...}, "timestamp": 1750000000.0,
  "correlation_id": "uuid", "metadata": {}
}
```

回复消息 topic 为 `{topic}.reply` 且携带原 correlation_id。传输层：进程内 / Redis Streams（`TRAVEL_*` 环境变量选择）。

---

## 6 需求核实与诚实性声明

1. 本文档所有 FR 的"验收标准"均可对应到仓库内真实测试用例或明确的代码行为；无自动化覆盖的项（FR-018 过滤链 HTTP 行为、FR-026 健康端点、OTel 导出链路）已在正文中显式标注。
2. 性能与容量指标（NFR-001/003）区分"目标口径"与"当前实测"，实测证据（`stress/report_kind.json`）显示目标**尚未达成**，文档不做达标声明。
3. 需求—设计—验证的完整映射见 `docs/traceability-matrix.md`；矩阵中的测试用例名均经 grep 核实存在。
