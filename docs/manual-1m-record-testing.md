# 100万记录场景人工测试运行手册（10B/1M 目标）

## 1. 当前结论（基于仓库最新证据）

当前状态：**未达到可宣称的生产级 10B 注册用户 / 100万并发已验证通过**。

证据来自：

- `stress/global_scale_readiness_report.json`
  - `status=ARCHITECTURE_READY_NOT_PROVEN`
  - `distributed_1m_evidence=false`
  - `global_multi_region_drill_evidence=false`
- `stress/distributed_benchmark_evidence.json`
  - `targetConcurrency=1000000`
  - `achievedConcurrency=300`
  - `pass=false`
- `stress/multi_region_fault_drill_report.json`
  - `scenarioCount=3`
  - `passedScenarios=2`
  - `pass=false`
  - 失败场景：`redis-cluster-failover`
- `stress/go_live_final_report.json`
  - 汇总门禁：`overall=PASS`
  - 说明：门禁脚本可通过，但并不等价于“100万并发真实压测已通过”。

## 2. 分级人工测试账户（Runtime 内部调用模型）

> 本项目运行时“账户”不是传统用户名密码登录模型，而是 `tenantId/userId/conversationId + internal headers + signature` 的内部调用模型。

### 2.1 必填 Header

- `X-Trace-Id`
- `X-Internal-Client-Id`
- `X-Internal-Signature`

默认值约束：

- `TRAVEL_INTERNAL_CLIENT_ID` 默认：`techgroup-enterprise-travel-gateway`
- `TRAVEL_INTERNAL_SHARED_SECRET` 默认：`demo-internal-secret`

签名算法（服务端校验）：

- `sha256(idempotencyKey + "." + shared_secret)`
- 接受“完整 digest”或“digest 前 16 位前缀”

示例（Python）：

```python
import hashlib

idem = "idem-basic-0001"
secret = "demo-internal-secret"
signature = hashlib.sha256(f"{idem}.{secret}".encode("utf-8")).hexdigest()
```

### 2.2 必填 Payload 字段

- `tenantId`
- `userId`
- `conversationId`
- `idempotencyKey`

建议同时显式传：

- `membershipTier`
- `allowedTools`
- `maxAgentSteps`
- `maxToolCalls`
- 业务字段：`city/days/budget/travelers/preferences`

### 2.3 账户等级矩阵（可直接用于人工测试）

| 账户级别 | tenantId | userId | membershipTier | 允许工具（默认策略） | 允许编排引擎（默认策略） | 主要测试目标 |
|---|---|---|---|---|---|---|
| L1-Basic | tenant-manual | user-basic | basic | search_hotels, search_transports, search_attractions | langgraph | 基础推荐链路、鉴权、限流 |
| L2-Silver | tenant-manual | user-silver | silver | basic + search_foods, search_activities | langgraph, agentscope | 扩展工具权限、引擎权限边界 |
| L3-Gold | tenant-manual | user-gold | gold | silver + search_events, search_souvenirs | langgraph, agentscope, oneagents | 全工具集、跨引擎一致性 |
| L4-Platinum | tenant-manual | user-platinum | platinum | 与 gold 相同 | 与 gold 相同 | 长时稳定性、并发与熔断边界 |

全局策略上限（默认）：

- `maxAgentSteps <= 50`
- `maxToolCalls <= 30`

> 重复提交同一个 `idempotencyKey` 会触发防重拒绝（`duplicate submission`），人工测试时必须每次更换。

## 3. 测试前准备（“已有100万记录”前提）

### 3.1 环境变量基线

至少确认：

- `TRAVEL_INTERNAL_SHARED_SECRET`
- `TRAVEL_INTERNAL_CLIENT_ID`
- `TRAVEL_MEMBERSHIP_REDIS_URL`（或 `TRAVEL_REDIS_URL`）
- `TRAVEL_REDIS_MODE=cluster`
- `TRAVEL_EVENT_BUS=pulsar`
- `TRAVEL_VECTOR_BACKEND=faiss|qdrant|milvus`

### 3.2 启动方式（任选）

Windows：

```powershell
powershell -ExecutionPolicy Bypass -File platform/deploy/scripts/one_click_stack_windows.ps1
```

Linux：

```bash
bash platform/deploy/scripts/one_click_stack_linux.sh
```

macOS：

```bash
bash platform/deploy/scripts/one_click_stack_macos.sh
```

## 4. 全链路人工测试步骤（服务 + DB/缓存/MQ + 压测 + 灾备）

### 步骤 A：基础设施连通性与健康

```bash
python platform/deploy/scripts/manual_infra_checks.py --out stress/manual_infra_checks_report.json
```

检查点：

- Runtime: `http://127.0.0.1:8000/health`
- Gateway: `http://127.0.0.1:8080/api/v1/travel/health`
- Web: `http://127.0.0.1:5173`
- Nacos / Qdrant / Pulsar Admin
- TCP: etcd(2379), pulsar(6650), redis-cluster(7000)

判定：`summary.overall=PASS`

---

### 步骤 B：分级账户功能与权限验证（L1~L4）

对四个账户分别调用 `/runtime/recommend`：

1. 正常请求（有效签名 + 唯一 idempotencyKey）应返回 200
2. 重放同一 `idempotencyKey` 应触发防重拒绝
3. 用 basic 账户请求高阶工具（如 `search_events`）应被策略过滤或拒绝
4. 引擎权限越权（如 basic + oneagents）应被拒绝

判定：权限、工具、引擎边界与 `membershipTier` 一致。

---

### 步骤 C：数据库/注册中心（etcd）人工验证

```bash
python stress/etcd_migration_drill.py \
  --legacy-base-url http://localhost:8000 \
  --new-base-url http://localhost:8001 \
  --requests 200 \
  --concurrency 20 \
  --out-json stress/etcd_migration_compare.json \
  --out-md stress/etcd_canary_report.md
```

判定：

- `stress/etcd_migration_compare.json` 中 `summary.consistency_status=pass`
- `stress/etcd_canary_report.md` 生成

> 说明：仓库当前没有 MySQL/PostgreSQL/Mongo 专用检查脚本；若生产使用这些数据库，请补充对应 count/慢查询/连接池人工验证流程。

---

### 步骤 D：缓存（Redis Cluster）人工验证

```bash
python stress/redis_cluster_scenarios.py
```

覆盖场景：

- 热点缓存
- 限流计数
- 幂等防重
- 分布式锁
- 用户画像缓存
- 行程快照
- 热门城市计数
- 最近搜索历史

判定：脚本完整执行且输出中无异常失败。

---

### 步骤 E：MQ / 事件总线（Pulsar）人工验证

```bash
python scripts/run_event_consumers.py --max-messages 200 --max-retries 3 --retry-backoff-ms 200
```

然后执行 canary 事件门禁：

```bash
python platform/deploy/scripts/canary_gate.py \
  --report stress/etcd_migration_compare.json \
  --event-metrics stress/pulsar_consumer_metrics.prom \
  --out stress/canary_gate_decision.json \
  --metrics-out stress/canary_gate_metrics.prom
```

判定：

- 消费指标 lag、DLQ 在阈值内
- `stress/canary_gate_decision.json` 为 promote（或至少满足当前阶段准入策略）

---

### 步骤 F：压测与 100万并发证据链

#### F1. 本地基线压测（非 100万 真证据）

```bash
python stress/load_test.py --base-url http://localhost:8000 --requests 2000 --concurrency 200 --out stress/report.json
```

#### F2. 外部压测结果导入（k6/JMeter/Locust）

```bash
python stress/distributed_benchmark_ingest.py \
  --input-json path/to/k6-summary.json \
  --schema k6 \
  --run-id run-1m-001 \
  --environment staging \
  --target-concurrency 1000000 \
  --regions 3 \
  --duration-minutes 60
```

判定（必须同时满足）：

- `stress/distributed_benchmark_evidence.json` 中
  - `pass=true`
  - `achievedConcurrency >= 1000000`
  - `regions >= 3`
  - `durationMinutes >= 60`

---

### 步骤 G：多地域故障演练 / DR 证据

可用外部故障演练结果导入：

```bash
python stress/fault_drill_evidence_ingest.py \
  --input-json path/to/fault-drill.json \
  --schema native \
  --run-id drill-1m-001 \
  --environment staging
```

或使用仓库脚本生成演练证据：

```bash
python stress/multi_region_fault_drill.py \
  --canary-decision stress/canary_gate_decision.json \
  --canary-metrics stress/canary_gate_metrics.prom \
  --incident-ticket stress/p3_5_incident_ticket.json
```

判定（必须同时满足）：

- `scenarioCount >= 3`
- `passedScenarios == scenarioCount`
- `redis-cluster-failover` 必须 PASS

---

### 步骤 H：最终准入门禁

先聚合 readiness：

```bash
python stress/global_scale_readiness.py --target-concurrency 1000000
```

再执行 go-live 最终门禁：

```bash
python platform/deploy/scripts/go_live_final_check.py \
  --min-scale-status PRODUCTION_PROVEN \
  --max-evidence-age-hours 24 \
  --allowed-evidence-environments staging,prod
```

最终通过标准：

- `stress/global_scale_readiness_report.json` 的 `status=PRODUCTION_PROVEN`
- `stress/go_live_final_report.json` 的 `summary.overall=PASS`

## 5. 交付物清单（人工测试完成后必须归档）

- `stress/manual_infra_checks_report.json`
- `stress/etcd_migration_compare.json`
- `stress/etcd_canary_report.md`
- `stress/pulsar_consumer_metrics.prom`
- `stress/canary_gate_decision.json`
- `stress/canary_gate_metrics.prom`
- `stress/distributed_benchmark_evidence.json` + `.md`
- `stress/multi_region_fault_drill_report.json` + `.md`
- `stress/global_scale_readiness_report.json` + `.md`
- `stress/go_live_final_report.json`

## 6. 当前待闭环项（对照本仓库现状）

要宣称“10B/1M 生产级已准备妥当且压测通过”，仍需完成：

1. 真实分布式压测达到并证明 `achievedConcurrency >= 1,000,000`
2. 多地域故障演练 3/3 全通过（当前 Redis failover 失败）
3. readiness 从 `ARCHITECTURE_READY_NOT_PROVEN` 提升为 `PRODUCTION_PROVEN`
4. （如生产有额外关系型/文档数据库）补齐 DB 专项人工验证脚本与证据
