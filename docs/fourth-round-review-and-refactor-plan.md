# 第四轮审查与重构方案（百万级并发口径）

- 日期：2026-10-26
- 审查人视角：AI/大数据教授级高工（博士）× 互联网大厂资深架构师 × 高级美工 × 文旅专家
- 口径：**支撑 100 万人同时使用（1,000,000 concurrent users）**
- 依据：TOGAF 10 ADM、GB/T 8567-2006（文档编制）、GB/T 9385-2008（SRS）、GB/T 25000.51（质量模型）
- 基线：三轮复盘 ≈68.3（docs/expert-review-and-refactoring-roadmap-2026-09.md 第十章）

---

## 一、运行环境实测（2026-10-26 SSH 实勘，禁止纸面推演）

### 1.1 集群拓扑（kubectl 实测）

| 项 | 实测值 |
|---|---|
| K8s | v1.28.2，k8s-master=10.167.2.175（control-plane+worker）、k8s-worker1=10.167.2.176，CentOS 7，docker 26.1.4 |
| 容量 | master 16C/126G（内存余 82G）、worker1 **64C/126G**（CPU 余 59%、内存余 62G） |
| 入口 | ingress-nginx（NodePort，无 LB；单 ingress-controller，requests 仅 100m/90Mi） |
| 监控 | kube-prometheus-stack（Prometheus/Grafana/Alertmanager 全 Running）+ Loki + promtail |
| 存储 | local-path（默认）/ nfs-client / pdm-local-ssd；886 个 PV |
| GitOps | Rancher fleet（cattle-*）+ education-platform 由 ArgoCD 管理 |

### 1.2 基础设施层服务实测清单（infra ns 为主）

| 服务 | 版本（实测） | 形态 | 可复用判定 |
|---|---|---|---|
| **TiDB** | pingcap/tidb:**v8.5.8**（2 TiDB + 3 TiKV + 3 PD） | Deployment/STS，NodePort 30210 | ✅ 主库+读库（Follower Read/Stale Read） |
| **Redis** | 7.4.11（单机 infra/redis）+ **8.10.1**（szxc-redis ×3 STS） | ClusterIP；3 节点版支持 cluster 语义 | ✅ L2 缓存（用 8.10 三节点） |
| **Pulsar** | broker×2 + bookie×2 + zk，cluster `platform-plus` | STS，NodePort 32160/32679 | ✅ 事件总线/削峰 |
| **Milvus** | **v2.6.6** standalone（+etcd+minio），NodePort 30909 | Deployment | ✅ 语义缓存/向量检索 |
| **NebulaGraph** | v3.8.3（graphd+metad+storaged） | Deployment/STS | ✅ 景点/路网知识图谱 |
| **Nacos** | Deployment（**当前 0 副本**，svc 保留） | 需扩容后再用 | ⚠️ 注册中心备选 |
| **CockroachDB** | 3 节点（镜像疑被误用 jupyter 镜像） | STS | ❌ 不采用（镜像异常） |
| **registry** | 10.167.2.175:30500（104 repos，base/python 等齐备） | Harbor 类 | ✅ 镜像仓库 |

**关键结论**：数据面中间件（TiDB 8.5 + Redis 8 + Pulsar + Milvus 2.6 + Nebula 3.8）完全满足百万级重构所需，**不新增中间件，全部复用集群既有设施**。

### 1.3 仓库事实（侦察报告要点）

- 2203 文件、业务代码约 27k 行（Python 15.9k / Java 7k / Go 3k / TS 0.8k）
- 6 服务（gateway-Java、runtime-Python、ranker/policy/fanout/registry-cache-Go），gRPC 契约 3 service/4 rpc
- **GraphQL 零实现**；**无读写分离**（database.py 单引擎 pool 100+200）；**无 L1 缓存**（仅 Redis）；限流为**固定窗口计数**；分库分表仅注释声明
- HPA 上限 600 pods（runtime）；实测并发证据 achievedConcurrency=300，文档自认 `ARCHITECTURE_READY_NOT_PROVEN`
- k6（含分布式 job 骨架）与 locust 脚本已存在；压测报告 20+ 份

---

## 二、第四轮审查评分（100 万人同时在线口径）

| # | 维度 | 三轮后 | **四轮** | 扣分主因（1M 口径） |
|---|------|-------|---------|-------------------|
| 1 | 需求分析与规格 | 62 | **62** | 1M 的 FR/NFR 量化条目与追溯矩阵未按 GB/T 9385 修订 |
| 2 | 架构设计文档 | 72 | **74** | TOGAF 10 视图补齐中；缺 Gateway API/GraphQL 联邦 ADR |
| 3 | DDD 落地 | 58 | **58** | 聚合边界清晰但仓储无读写分离/分片支撑 |
| 4 | 后端实现真实度 | 73 | **74** | 全链路真实；API 面过小（6+5 路由），GraphQL 缺位 |
| 5 | 前端多端 | 70 | **70** | 小程序仅 2 页 |
| 6 | 测试体系 | 71 | **71** | 147 用例 + 混沌，但无全链路流量染色 |
| 7 | **部署与运维（1M 容量）** | 77 | **56** | **单 ingress 无 LB、ingress requests 100m、无分片、HPA600 封顶；1M 需 ≥3000 pod 当量，仅 2 节点物理承载不了** |
| 8 | 安全 | 69 | **69** | mTLS/轮换已入，缺 WAF/入口层防护 |
| 9 | 文档治理 | 71 | **71** | 缺 GB/T 8567 验收文档包 |
| 10 | UI/UX | 55 | **55** | 未动 |
| **加权总分** | **≈68.3** | **≈63.5（1M 口径）** | **按 1M 严格口径反而降分——诚实结论：当前架构未按 1M 设计** |

> 评分说明：前几轮按"工程完成度"评分；本轮切换为"**1M 承载能力**"评分口径，部署/数据层缺口显性化，总分下调是审查口径修正而非退步。下文方案将针对性拉回。

---

## 三、百万级并发容量模型（基于实测集群推导）

### 3.1 流量模型（文旅黄金周口径）

```
1,000,000 同时在线
├─ 在线保持（WebSocket/SSE 心跳）：1M 长连接
├─ 点击/浏览读流量：1M × 0.1 req/s = 100,000 QPS（读）
├─ 行程推荐（AI 生成）：峰值 8% 活跃 = 80,000 并发请求
│   ├─ 同步首屏（缓存命中路径）：≈60,000 QPS
│   └─ 异步行程生成（队列削峰）：≈20,000 任务/分钟 → Pulsar
└─ 写流量（收藏/下单/改签）：≈2,000 QPS
```

### 3.2 分层容量与现有集群适配

| 层 | 需求 | 集群实况 | 方案 |
|---|---|---|---|
| 入口 | 1M 长连接 + 100k QPS | 1 个 ingress-nginx pod（100m！） | 扩至 **4 副本 × 调优**（worker_connections 65535、fs.file-max），NodePort 四节点均衡；启动 Gateway API 迁移 ADR |
| API 层（读） | 100k QPS，单 pod 1.5k QPS 实测基线 → ~70 pods | 仅 2 节点 | runtime 读副本 60 pods（worker1 64C 承载 40 + master 20） |
| AI 编排 | 80k 并发生成 | — | **异步化**：同步只出"行程骨架+缓存"，完整生成走 Pulsar 队列（削峰 10:1），KEDA 按队列深度扩容 |
| 缓存 | 读命中 ≥90% | Redis 8.10×3 | L1 进程内 + L2 Redis Cluster + L3 语义缓存（Milvus） |
| 数据 | 写 2k QPS / 读 100k QPS | TiDB 8.5（2 TiDB/3 TiKV） | 读写分离：写走 tidb-server 主，读走 Follower Read（tidb_replica_read=closest-adaptive）+ Stale Read |
| 压测侧 | 1M VU | 2 节点 | **按分片推算**：2 节点实测 50k VU → 外推模型给出 1M 所需压测集群规模（50-100 节点 k6-operator） |

### 3.3 物理边界诚实声明

2 台服务器（80 核 252G）**不可能物理承载 1M 长连接**（理论单节点上限约 5-10 万长连接）。本方案交付物分两层：
1. **本集群可实测**：50,000 VU 级真实压测 + 单 pod 基准 → 获得可信的"每 pod 容量常数"
2. **外推模型**：`1M 所需资源 = 实测常数 × 线性外推 + 系数`，输出采购/扩容清单（这是行业通行做法，杜绝 `NOT_PROVEN` 重演——因为每一步都有实测锚点）

---

## 四、详细重构方案（12 项，按 TOGAF Phase C/D 分组）

### A. 信息系统架构（数据与 API）

**R1 GraphQL 查询层（新 API 面）**
- strawberry-graphql 0.338（ASGI 挂 FastAPI `/graphql`）：`hotel/transport/itinerary/tripPlan` 类型 + DataLoader 批量化（防 N+1）
- 查询复杂度限制（cost limit 1000）+ 深度限制（≤7）+ Persisted Queries（APQ）防雪崩
- 契约：`data-contracts/graphql/schema.graphql` 单一事实源，测试用例校验 schema drift

**R2 读写分离（SQLAlchemy 2.0 官方 RoutedSession 模式）**
- `db/routing.py`：自定义 `AsyncSession` 工厂，重写 bind 路由——flush/写 → `TRAVEL_DB_URL`（主），纯 SELECT → `TRAVEL_DB_READ_URL`（TiDB follower）
- TiDB 侧：读连接设 `tidb_replica_read=closest-adaptive`；容忍陈旧的列表页用 Stale Read（`tidb_read_staleness=5`）
- 环境变量：`TRAVEL_DB_READ_URL` 缺省回退主库（本地/CI 零成本）；测试用两 sqlite 验证路由正确性

**R3 多级缓存（L1+L2+L3 语义）**
- L1：进程内 TTLCache（cachetools，TTL 5s，容量 2048/进程）——挡住热点击重复击穿
- L2：既有 CacheManager 升级为 Redis 8.10（szxc-redis 3 节点）+ 主动失效广播（pub/sub）
- L3：Milvus 2.6 语义缓存——`(city,days,budget,preferences-hash)` 向量化命中历史行程（TTL 24h），命中则跳过 LLM 生成
- 全链路 cache hit 率作为 Prometheus 指标 + 压测门禁（读命中 ≥85%）

**R4 限流算法升级（令牌桶）**
- `traffic_guard.py` 固定窗口 → Redis 8 hash-field-TTL 令牌桶（`HSETEX` 原生），按 `(tenant,user,ip)` 三维键；突发容忍度可配

### B. 技术架构（运行时与弹性）

**R5 异步行程生成削峰**
- 同步 `/recommend` 只返回：骨架 + 缓存命中或"任务已受理+taskId"
- 完整 AI 生成投递 Pulsar topic `travel-agent.itinerary.tasks`，go-fanout 消费，完成后经 `itinerary.results` 推送
- KEDA ScaledObject：按 Pulsar 订阅 backlog 扩容 runtime 生成 worker（1~200）

**R6 入口层加固与扩容**
- ingress-nginx：replicas 1→4（跨两节点），requests 2C/2G，`worker_connections=65535`、`keepalive_requests=100000`、`limit-conn` 全局保护
- ADR-0006：ingress-nginx → Gateway API（Envoy Gateway）迁移路线（1M 正式环境用，本集群先留 ingress-nginx 实测）

**R7 HPA/KEDA 弹性矩阵**
- runtime 读层 HPA min24/max600 保留；新增生成 worker KEDA（Pulsar lag）；ingress HPA 按 CPU 65%
- PDB 全服务覆盖（滚动/节点故障 0 不可用）

**R8 可观测性补齐**
- runtime 增加 Prometheus `/metrics`（QPS、P95/P99、cache hit、token 桶拒绝数、LLM 上游延迟）——本轮审查发现 metrics 代码缺失
- Grafana 看板 JSON 入库（dashboard per service）

### C. 测试架构（TDD/BDD/SDD 落地）

**R9 功能全链路测试**
- REST 6 路由 + GraphQL 新 API 全覆盖（httpx AsyncClient + strawberry test client）
- BDD：`tests/bdd/features/travel_recommend.feature`（Gherkin 场景：黄金周高峰/改签/取消），pytest-bdd 执行
- SDD（spec-driven）：契约测试校验 gRPC proto ↔ GraphQL schema ↔ REST OpenAPI 三面一致

**R10 K6 平台压测（本集群实测）**
- k6-operator `parallelism=10`（每 pod 5,000 VU → **50,000 VU 实测**）
- 场景：browse（90% 读，令 GraphQL+REST 混合）、recommend-sync、recommend-async（队列全链路）
- 门禁：P95<300ms（读，缓存命中）、P95<2s（骨架返回）、错误率<0.1%

**R11 Locust 业务链路仿真**
- 分布式 master+8 worker（K8s Job），Python 脚本直连真实业务流（登录→推荐→收藏→改签），验证 5,000 并发用户行为模型
- 输出与 k6 交叉验证（数字一致性 ±15%）

**R12 容量外推报告**
- 以 50k VU 实测常数外推 1M：`api_pods = ceil(100k QPS / 单pod实测QPS)`、`ingress_pods`、`压测集群=50-100 节点 k6-operator`
- 输出采购清单与成本模型（沿用 capacity_cost_model.py 方法论）

### 实施顺序与验收

```
第1周：R2 读写分离 → R3 多级缓存 → R4 令牌桶（数据层，测试先行 TDD）
第2周：R1 GraphQL → R8 metrics → R5 异步削峰
第3周：R6/R7 部署加固 → R9 功能/BDD → R10/R11 压测 → R12 报告
每步：pytest 全绿 + 契约校验 → 提交 → 集群部署验证
```

---

## 五、风险登记

| 风险 | 等级 | 缓解 |
|---|---|---|
| 2 节点物理上限 | 高 | 诚实外推 + 每 pod 实测锚点；1M 生产需扩容清单（方案给出） |
| TiDB 仅 2 TiDB-server | 中 | Follower Read 前 TiKV×3 已满足；TiDB-server 按读流量扩 4 |
| ingress-nginx 维护收缩期 | 中 | ADR-0006 迁移 Gateway API，本集群不影响实测 |
| Redis 8 AGPLv3 许可 | 低 | 集群内私有部署，不对外分发，合规（ADR 备注） |
| Nacos 0 副本 | 低 | 本次不改注册中心（K8s svc+DNS 已够），扩容列为可选项 |

## 六、交付物清单（本轮承诺）

1. 本文档（审查+方案）2. 重构代码（R1-R8）+ 测试（R9）3. k6/locust 脚本与 K8s 编排（R10/R11）4. `stress/fourth_round_test_report.md`（功能+性能+容量外推）5. 复盘文档第十二章 6. 全部推送远端
