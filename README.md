# Enterprise Travel Recommender Agent

企业级智能旅游推荐智能体（原型实现）：

- 分布式多 Agent 协同（Manager / RouteMaking / TripPlanner）
- 业务粘性扩展 Agent（Food / LocalEvent / LoyaltyGrowth / WeatherRisk / AncillaryRevenue）
- MCP Gateway 风格工具调用（酒店、交通、景点）
- Skills 动态加载（按技能绑定可调用工具）
- 可测试、可部署（Docker Compose + K8s 清单）

## CI 快速入口（TechGroup）

```bash
npm run ci:test:python
npm run ci:test:gateway
npm run ci:test:all
```

命名规范与企业级约束见：`docs/technology-group-naming-convention.md`。

10B 用户 / 10M 并发为**容量规划目标**（非实测结论），规划方案见：`docs/industrial-scale-upgrade-plan-10b-10m.md`。

100万并发 readiness 评估（本地证据聚合；当前实测状态为 ARCHITECTURE_READY_NOT_PROVEN）：

```bash
python stress/global_scale_readiness.py --target-concurrency 1000000
```

输出：`stress/global_scale_readiness_report.json` 与 `stress/global_scale_readiness_report.md`。

推到 `PRODUCTION_PROVEN` 的证据链（分布式压测 + 异地多活故障演练）：

```bash
export TRAVEL_EVIDENCE_SIGNING_KEY="replace-with-strong-key"
python stress/distributed_benchmark_ingest.py --input-json stress/report_5k.json --run-id 2026M04D02-benchmark --environment staging --regions 3 --duration-minutes 60
python stress/fault_drill_evidence_ingest.py --input-json stress/multi_region_fault_drill_report.json --run-id 2026M04D02-drill --environment staging
python stress/global_scale_readiness.py --target-concurrency 1000000
python platform/deploy/scripts/go_live_final_check.py --min-scale-status PRODUCTION_PROVEN --max-evidence-age-hours 24 --allowed-evidence-environments staging,prod
```

真实外部证据接入（推荐）：

```bash
export TRAVEL_EVIDENCE_SIGNING_KEY="replace-with-strong-key"
python stress/distributed_benchmark_ingest.py --input-json stress/report_5k.json --run-id 2026M04D02-benchmark --environment staging
python stress/fault_drill_evidence_ingest.py --input-json stress/multi_region_fault_drill_report.json --run-id 2026M04D02-drill --environment staging
python platform/deploy/scripts/go_live_final_check.py --min-scale-status PRODUCTION_PROVEN --max-evidence-age-hours 24 --allowed-evidence-environments staging,prod
```

本地生活推荐能力：

- 已有 `food-recommendation-agent`、`local-event-agent`
- 新增 `local-lifestyle-agent`（活动 + 特产/伴手礼）
- 新增工具：`search_activities`、`search_souvenirs`

Iceberg/Flink/数据飞轮设计与落地入口：`docs/data-flywheel-lakehouse-design.md`

GraphRAG + Faiss 已升级为必选（非可选）：

- 依赖已进入 `requirements.txt`
- 环境模板默认 `TRAVEL_MEMORY_BACKEND=vector`、`TRAVEL_VECTOR_BACKEND=faiss`、`TRAVEL_VECTOR_STRICT=true`
- `go_live_final_check.py` 默认启用 `faiss_dependency_present` 硬门禁

Flink + Iceberg（Hive/Glue/Nessie）与训练/特征回流 SLA 统一门禁：

- Flink/Iceberg 配置校验：`platform/deploy/scripts/validate_flink_iceberg_config.py`
- 数据飞轮 SLA 报告：`stress/flywheel_sla_report.py`
- 统一门禁脚本：`platform/deploy/scripts/go_live_final_check.py`

一键部署/压测/人工中间件检查脚本：

- Windows: `platform/deploy/scripts/one_click_stack_windows.ps1`
- Linux: `platform/deploy/scripts/one_click_stack_linux.sh`
- macOS: `platform/deploy/scripts/one_click_stack_macos.sh`
- 人工基础设施检查: `platform/deploy/scripts/manual_infra_checks.py`

## 1. Architecture Choice

本项目按“生产建议架构”实现 MVP：

- **Agent Runtime 思路：LangGraph 风格状态工作流**（本仓库用 Python 原生实现同类编排能力）
- **企业接入层：Spring AI Alibaba 思路**（在文档中给出企业级 Java 接入与替换方案）
- **互操作边界：MCP Gateway**（工具注册、schema、调用审计）

## 2. Project Structure

```text
enterprise-travel-agent/
├─ docs/
│  ├─ framework-comparison.md
│  ├─ system-design.md
│  └─ deployment-and-testing.md
├─ data/
│  ├─ hotels.json
│  ├─ transports.json
│  └─ attractions.json
├─ skills/
│  ├─ budget.skill.json
│  ├─ comfort.skill.json
│  └─ family.skill.json
├─ services/techgroup-enterprise-travel-runtime/src/travel_agent/
│  ├─ api/app.py
│  ├─ agents/
│  ├─ mcp/
│  ├─ discovery/
│  ├─ a2a/
│  ├─ recommendation/
│  ├─ skills/
│  ├─ tools/
│  └─ run_demo.py
├─ tests/
├─ platform/deploy/
│  ├─ docker-compose.yml
│  └─ k8s/
└─ pyproject.toml
```

## 3. Quick Start

Python baseline: **3.12+**

```bash
cd "enterprise-travel-agent"
python3 -m unittest discover -s tests -p "test_*.py" -v
PYTHONPATH=services/techgroup-enterprise-travel-runtime python3 -m src.travel_agent.run_demo
```

### 可插拔编排引擎（A2A/MCP/Skills/Harness增强）

默认引擎为 `langgraph`（当前最稳妥，图编排能力与生态成熟度更适合生产首选）。可通过环境变量切换到适配器模式：

```bash
export TRAVEL_ORCHESTRATION_ENGINE=langgraph   # local|langgraph|agentscope|oneagents
```

`local/native` 不再作为独立执行引擎；选择该模式时会按 fallback 配置自动切换。

```bash
export TRAVEL_ORCHESTRATION_FALLBACK_ENGINE=langgraph  # langgraph|agentscope|oneagents
export TRAVEL_ORCHESTRATION_STRICT=false               # true 时未知引擎报错
```

可选框架依赖（按需安装）：

```bash
pip install -r requirements-orchestration-optional.txt
```

说明：`langgraph/agentscope/oneagents` 当前以适配器模式接入，保持本地编排链路可回退。

并行灰度观测（推荐在 staging/prod 开启）：

```bash
export TRAVEL_ORCHESTRATION_ENGINE=langgraph
export TRAVEL_ORCHESTRATION_SHADOW_ENGINE=agentscope
```

启用后会新增事件：`recommend.engine_shadow_compared`，用于主/影子引擎观测对比。

A2A 分布式传输配置：

```bash
export TRAVEL_A2A_TRANSPORT=redis
export TRAVEL_A2A_REDIS_URL=redis://localhost:7000
export TRAVEL_A2A_STREAM_GROUP=a2a-consumers
export TRAVEL_A2A_PENDING_RETRY_IDLE_MS=10000
export TRAVEL_A2A_AUDIT_MIRROR_PULSAR=true
export TRAVEL_A2A_AUDIT_TOPIC=persistent://public/default/travel-agent.a2a.audit
```

测试场景可使用 `TRAVEL_A2A_TRANSPORT=mock-distributed`。

A2A 运行态运维脚本：

- 导出 Streams 指标：`python platform/deploy/scripts/export_a2a_stream_metrics.py`
- 审计回放核验：`python stress/a2a_audit_replay_check.py --file var/events/a2a_audit_events.jsonl`

三环境模板：

- `platform/deploy/env/dev.env`
- `platform/deploy/env/staging.env`
- `platform/deploy/env/prod.env`

Harness 回放能力（用于 A2A/MCP/Skills 编排链路回归）已内置：

- 每次推荐都会记录最近编排样本
- 可通过 orchestrator 的 `replay_last_harness_case()` 执行回放验证

### 注册中心切换

```bash
export TRAVEL_REGISTRY=nacos-real  # or etcd-real
```

真实集群（默认）：

```bash
export TRAVEL_REGISTRY=nacos-real
export NACOS_SERVER_ADDR=http://localhost:8848

# or
export TRAVEL_REGISTRY=etcd-real
export ETCD_HOST=localhost
export ETCD_PORT=2379
export TRAVEL_ETCD_CLIENT_MODE=legacy  # legacy|new|auto
```

Etcd 双栈迁移（新旧兼容）：

- 默认安装 legacy 客户端：`pip install -r requirements.txt -r requirements-etcd-legacy.txt`
- 新客户端试运行：`pip install -r requirements.txt -r requirements-etcd-new.txt`
- 通过 `TRAVEL_ETCD_CLIENT_MODE=legacy|new|auto` 选择运行模式

严格模式（生产建议）：

```bash
export TRAVEL_REGISTRY_FAIL_FAST=true
```

### 记忆存储（Memory）

默认使用内存存储（无需依赖）。支持三类后端：

- `TRAVEL_MEMORY_BACKEND=memory`：默认内存消息存储
- `TRAVEL_MEMORY_BACKEND=redis`：Redis 列表存储 + TTL
- `TRAVEL_MEMORY_BACKEND=vector`：本地轻量语义检索（token 相似度）
- `TRAVEL_MEMORY_BACKEND=rocksdb`：RocksDB 持久化（需显式依赖与路径）

Redis 示例：

```bash
export TRAVEL_MEMORY_BACKEND=redis
export TRAVEL_REDIS_MODE=cluster
export TRAVEL_REDIS_URL=redis://localhost:7000
```

Redis 使用场景扩展（已实现）：

- 热点目的地攻略缓存（`hot_plan:*`）
- 用户限流（`rate_limit:user:*`）
- 幂等键去重（`idempotency:*`）
- 分布式锁（`lock:*`）
- 用户画像缓存（`profile:*`）
- 行程快照缓存（`itinerary:*`）
- 热门城市计数（`city_popularity:*`）
- 最近搜索历史（`recent_search:*`）

GraphRAG + Faiss（必选）：

```bash
pip install -r requirements.txt
export TRAVEL_MEMORY_BACKEND=vector
export TRAVEL_VECTOR_BACKEND=faiss
export TRAVEL_VECTOR_STRICT=true
```

会员分级权限（`membershipTier`）：

- `basic`：基础推荐工具
- `silver`：增加餐饮工具与 AgentScope 可用权限
- `gold/platinum`：解锁活动工具、管家智能体与更多编排引擎

RocksDB 示例：

```bash
export TRAVEL_MEMORY_BACKEND=rocksdb
export TRAVEL_ROCKSDB_PATH=/tmp/travel-agent-memory.rocksdb
```

Vector 示例：

```bash
export TRAVEL_MEMORY_BACKEND=vector
```

Runtime API 需要 `tenantId/userId/conversationId` 以隔离记忆域。
返回字段包含 `memory_before`、`memory_after`、`memory_hits`（语义检索结果）。

示例输出会给出：

- 酒店推荐（评分+理由）
- 交通推荐（性价比/舒适度）
- 3日行程建议（景点+时段）

## 4. Optional API Mode

若安装 FastAPI：

```bash
pip3 install fastapi uvicorn
PYTHONPATH=services/techgroup-enterprise-travel-runtime python3 -m uvicorn src.travel_agent.api.app:app --reload --port 8000
```

`POST /recommend` 输入旅行偏好，返回完整推荐结果。

## 5. Spring Gateway Upgrade

新增 `techgroup-enterprise-travel-gateway/` 子项目，作为企业级入口与策略控制层：

- 统一入口：`/api/v1/travel/recommend`
- 策略校验：`allowedTools`、`maxAgentSteps`、`maxToolCalls`
- 转发 Python Runtime：`/runtime/recommend`

### Gateway 启动（需要 JDK17 + Maven）

```bash
cd techgroup-enterprise-travel-gateway
mvn spring-boot:run
```

### Keycloak OIDC 鉴权（已接入）

- 部署 Keycloak（Compose 已含服务，控制台 `http://localhost:8081`，realm 导入：`platform/deploy/keycloak/realm-travel.json`）
- 预置演示账号：`demo-basic` / `demo-silver` / `demo-gold`（密码 `demo-pass-123`，分别绑定会员等级角色）
- Gateway 作为 OAuth2 资源服务器校验用户 JWT（`TRAVEL_SECURITY_MODE=oauth2`，本地 off 时门禁会告警）
- Gateway→Runtime 内部调用使用 HMAC-SHA256 全量签名（绑定 clientId，密钥 `TRAVEL_INTERNAL_SHARED_SECRET`，禁止沿用 demo 值上 staging/prod）
- Runtime JWT 验签模块：`services/techgroup-enterprise-travel-runtime/src/travel_agent/api/auth.py`（JWKS 缓存 + RS256 + iss/aud/exp 校验）

### Spring AI Alibaba（已接入）

- `spring-ai-alibaba-agent-framework`
- `spring-ai-alibaba-starter-dashscope`
- 通过 `ChatClient.Builder` 生成推荐解释（AI rationale）

## gRPC 合约与代码生成

内部高频链路已补齐 v1 proto 合约：

- `data-contracts/grpc/v1/runtime.proto`
- `data-contracts/grpc/v1/policy.proto`
- `data-contracts/grpc/v1/ranker.proto`
- `data-contracts/grpc/v1/common.proto`

一键生成 Python/Go stubs：

```bash
python scripts/generate_grpc_stubs.py
```

生成 Gateway Java stubs：

```bash
cd services/techgroup-enterprise-travel-gateway
mvn generate-sources
```

Windows（仓库路径包含中文）建议使用脚本，自动做 `subst` 映射避免 `protobuf-maven-plugin` 路径编码问题：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/generate_grpc_java_stubs.ps1
```

gRPC 合约漂移检查（CI 同步执行）：

```bash
python scripts/check_grpc_stub_drift.py
```

Go Ranker 双栈端口：

- HTTP: `GO_RANKER_PORT`（默认 `8090`）
- gRPC: `GO_RANKER_GRPC_PORT`（默认 `9090`）

Runtime 到 Go Ranker 传输配置：

- `TRAVEL_GO_RANKER_TRANSPORT=auto|grpc|http`（默认 `auto`）
- `TRAVEL_GO_RANKER_GRPC_TARGET=host:port`（默认 `localhost:9090`）
- `TRAVEL_GO_RANKER_GRPC_FALLBACK_HTTP=true|false`（默认 `true`）

`auto` 与 `grpc` 模式会优先走 gRPC；若失败则按 fallback 策略回退 HTTP。

Ranker 传输可观测指标（Prometheus 文本文件）默认输出到：

- `stress/ranker_transport_metrics.prom`

关键指标：

- `travel_ranker_grpc_attempt_total` / `travel_ranker_grpc_success_total` / `travel_ranker_grpc_error_total`
- `travel_ranker_http_attempt_total` / `travel_ranker_http_success_total` / `travel_ranker_http_error_total`
- `travel_ranker_fallback_http_total`
- `travel_ranker_shadow_diff_total`

发布上线源码加密/混淆（Release Hardening）：

```bash
export TRAVEL_RELEASE_HARDENING=true
export TRAVEL_RELEASE_SOURCE_KEY="replace-with-strong-secret"
bash platform/deploy/scripts/build_release.sh
```

生成产物：`var/release_hardening/source_protection_manifest.json` 与 `var/release_hardening/encrypted_sources/**.enc`。

配置模型 Key（可选）：

```bash
export AI_DASHSCOPE_API_KEY="your_key"
```

未配置 Key 时系统会自动使用本地回退解释，不影响主流程演示。

### 课程级图文文档

见 `docs/course-delivery.md`（含 Mermaid 架构图、时序图、部署拓扑图、评分矩阵、案例附录）。

## 6. MCP / Agent / A2A 当前落点

- MCP 工具注册：`services/techgroup-enterprise-travel-runtime/src/travel_agent/mcp/registry.py`
- Agent + 工具目录注册中心：`services/techgroup-enterprise-travel-runtime/src/travel_agent/discovery/*`
- A2A 协议与路由：`services/techgroup-enterprise-travel-runtime/src/travel_agent/a2a/protocol.py` + `services/techgroup-enterprise-travel-runtime/src/travel_agent/a2a/router.py`

## 7. 压测

```bash
python3 stress/load_test.py --base-url http://localhost:8000 --requests 2000 --concurrency 200 --out stress/report.json
```

结果会输出成功率、平均延迟、p95/p99与状态码分布。

Redis Cluster 场景演练（缓存/限流/锁/幂等）：

```bash
python3 stress/redis_cluster_scenarios.py
```

分布式压测方案见：`stress/distributed-plan.md`

Etcd 客户端迁移演练（legacy/new 一致性对比）：

```bash
python3 stress/etcd_migration_drill.py \
  --legacy-base-url http://localhost:8000 \
  --new-base-url http://localhost:8001 \
  --requests 200 \
  --concurrency 20
```

可产出：

- `stress/etcd_migration_compare.json`
- `stress/etcd_canary_report.md`

## 8. PPT 与微课视频产物

### 100页公开分享PPT

```bash
node scripts/build_public_ppt_100.js
```

产物：

- `deliverables/Enterprise_Travel_Agent_Public_Deck_100p.pptx`

### 100页演讲备注版PPT

```bash
node scripts/build_public_ppt_100_notes.js
```

产物：

- `deliverables/Enterprise_Travel_Agent_Public_Deck_100p_Notes.pptx`

备注格式与 v2 版一致：

- `[开场句]`
- `[过渡句]`
- `[1分钟讲法]`
- `[Q&A提示]`

### 微课视频（含字幕烧录）

```bash
python3 video/microcourse/tools/generate_narration.py
python3 video/microcourse/tools/render_microcourse.py
python3 video/microcourse/tools/render_microcourse_html.py
```

产物：

- `video/microcourse/output/microcourse.mp4`
- `video/microcourse/output/microcourse_with_subtitles.mp4`
- `video/microcourse/output/microcourse_standalone.html`

## 9. Web 前端与微信小程序端

当前仓库已补齐：

- Web 前端：`apps/techgroup-enterprise-travel-web/`（React 19 + Vite + TanStack Query + Axios）
- 微信小程序：`miniapp-wechat/`（原生小程序结构，可直接在微信开发者工具导入）

### Web 端启动

```bash
cd apps/techgroup-enterprise-travel-web
npm install --include=dev
npm run dev
```

默认接口地址：`http://localhost:8080`，可通过环境变量覆盖：

```bash
VITE_TRAVEL_API_BASE_URL=http://localhost:8080
```

### 微信小程序端

1. 打开微信开发者工具
2. 导入目录：`miniapp-wechat/`
3. 在 `miniapp-wechat/utils/api.js` 设置网关地址（默认 `http://localhost:8080`）
4. 将后端域名加入小程序合法请求域名

生产增强点：

- Web：本地 session 默认值持久化、token 注入、网关错误映射、5xx/网络重试
- Mini Program：请求重试、状态码错误映射、强校验、卡片化结果展示

### 全栈本地联调（Docker Compose）

```bash
cd platform/deploy
docker compose up
```

包含服务：

- Python Runtime API: `http://localhost:8000`
- Spring Gateway: `http://localhost:8080`
- Web Frontend: `http://localhost:5173`
- Nacos: `http://localhost:8848`
- Etcd: `http://localhost:2379`

## 10. 上线与发布治理

- Go-Live Checklist: `docs/go-live-checklist.md`
- Release Runbook: `docs/release-runbook.md`
- Global Active-Active Plan: `docs/global-active-active-deployment-plan.md`
- Policy-Core Design: `docs/policy-core-design.md`
- Core Modules Alignment: `docs/core-modules-alignment.md`
- Nginx ingress template: `platform/deploy/nginx/nginx.conf`

A2A 监控与可视化资产：

- K8s CronJob: `platform/deploy/k8s/a2a-metrics-cronjob.yaml`
- Grafana Dashboard: `platform/deploy/monitoring/grafana-dashboard-a2a-stream-pulsar.json`

会员与流量防护（Runtime）：

- 分布式会员存储：`TRAVEL_MEMBERSHIP_REDIS_URL`
- 限流：`TRAVEL_RATE_LIMIT_PER_MINUTE`, `TRAVEL_RATE_LIMIT_WINDOW_SEC`
- 幂等去重：`TRAVEL_IDEMPOTENCY_TTL_SEC`
- 熔断：`TRAVEL_CIRCUIT_FAIL_THRESHOLD`, `TRAVEL_CIRCUIT_COOLDOWN_SEC`

## 11. 上线前最后加固

### Web 路由与权限页

- `/login`：登录页
- `/app`：受保护业务页
- `/forbidden`：权限拒绝页

### 小程序分包与埋点

- 主包：`pages/index/index`
- 分包：`pkg/insights/pages/metrics/index`
- 埋点工具：`miniapp-wechat/utils/analytics.js`

### 生产发布脚本包（运维可直接执行）

目录：`platform/deploy/scripts/`

- `preflight.sh`
- `build_release.sh`
- `deploy_release.sh`
- `healthcheck_release.sh`
- `rollback_release.sh`

运维交接文档：`docs/ops-production-handoff.md`

## 12. Go 性能升级模块（企业级可选）

建议优先引入 Go 的模块（按收益排序）：

1. 评分/排序（Scoring/Ranking）
2. 聚合并发请求（Fanout/Aggregation）
3. 注册发现缓存（Registry Cache）
4. 策略检查运行时（Policy Runtime）

本项目已完成第一阶段落地：

- 新增 Go Ranker 服务：`services/techgroup-enterprise-travel-ranker-go/`
- 默认仍走 Python 评分（安全回退）
- 可通过环境变量启用 Go 评分：

```bash
export TRAVEL_RANKER_BACKEND=go
export TRAVEL_GO_RANKER_URL=http://localhost:8090
export TRAVEL_GO_RANKER_TIMEOUT=0.4
```

Go 服务启动：

```bash
cd services/techgroup-enterprise-travel-ranker-go
go mod tidy
go run main.go
```

Shadow 对比监控（Go/Python 分差）：

```bash
export TRAVEL_GO_RANKER_SHADOW=true
export TRAVEL_GO_RANKER_DIFF_THRESHOLD=0.08
```

## 13. K8s 生产清单（标准集群规格）

新增清单：

- Ingress: `platform/deploy/k8s/ingress.yaml`
- TLS Secret 模板: `platform/deploy/k8s/tls-secret.yaml`
- API PDB: `platform/deploy/k8s/pdb.yaml`
- Go Ranker Deployment/Service/HPA/PDB:
  - `platform/deploy/k8s/go-ranker-deployment.yaml`
  - `platform/deploy/k8s/go-ranker-service.yaml`
  - `platform/deploy/k8s/go-ranker-hpa.yaml`
  - `platform/deploy/k8s/go-ranker-pdb.yaml`

同时已在 API Deployment 注入 Go Ranker 开关变量，支持金丝雀/灰度启用。

## 14. Kustomize 一键环境化发布

路径：`platform/deploy/k8s/kustomize/`

```bash
# dev
kubectl apply -k platform/deploy/k8s/kustomize/overlays/dev

# staging
kubectl apply -k platform/deploy/k8s/kustomize/overlays/staging

# prod
kubectl apply -k platform/deploy/k8s/kustomize/overlays/prod
```

## 15. Go 扩展模块（fanout / policy / registry cache）

- go-fanout: `services/techgroup-enterprise-travel-fanout-go/`
- go-policy: `services/techgroup-enterprise-travel-policy-go/`
- go-registry-cache: `services/techgroup-enterprise-travel-registry-cache-go/`

详细说明：`docs/go-expansion-guide.md`

Canary 分流开关（Go / Python）：

```bash
# ranker
export TRAVEL_RANKER_BACKEND=canary
export TRAVEL_RANKER_CANARY_PERCENT=10

# policy
export TRAVEL_POLICY_BACKEND=canary
export TRAVEL_POLICY_CANARY_PERCENT=10
```

Canary 自动门禁：

```bash
python3 platform/deploy/scripts/canary_gate.py --report stress/etcd_migration_compare.json
bash platform/deploy/scripts/canary_promote_or_rollback.sh stress/etcd_migration_compare.json
```

## 16. 监控与告警（PrometheusRule + Grafana）

新增监控资产：

- PrometheusRule: `platform/deploy/monitoring/prometheus-rule.yaml`
- Grafana Dashboard: `platform/deploy/monitoring/grafana-dashboard-go-runtime.json`

已纳入 kustomize base：

```bash
kubectl apply -k platform/deploy/k8s/kustomize/overlays/dev
```

Canary gate 指标化：

- 默认写入：`stress/canary_gate_metrics.prom`
- 可选 Pushgateway：通过环境变量注入

```bash
export CANARY_GATE_PUSHGATEWAY_URL=http://pushgateway.monitoring.svc:9091
export CANARY_GATE_PUSHGATEWAY_JOB=canary_gate
bash deploy/scripts/canary_promote_or_rollback.sh stress/etcd_migration_compare.json
```

可导出指标包括：

- `canary_gate_status`（1=promote, 0=rollback）
- `canary_gate_success_rate_gap`
- `canary_gate_p95_drift_ratio`
- `canary_gate_p99_drift_ratio`
- 对应阈值与最近评估时间戳指标
