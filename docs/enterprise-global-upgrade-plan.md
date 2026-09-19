# 企业级终极升级方案（全球多活 / 10B用户 / 10M并发目标）

## 1) 是否要把 Java 全部改成 Go？

结论：**不建议“一刀切重写”**。建议保持多语言分层架构：

- Java（Spring Gateway）：入口治理、鉴权、策略、审计、对外契约稳定。
- Python（Agent Runtime）：模型编排、技能加载、业务策略快速迭代。
- Go（Fanout/Ranker/Policy）：高并发网络扇出、计算重排、策略执行。

为什么不全改：

1. 重写会引入巨大回归风险，且无法直接带来 10M 并发收益。
2. 真正瓶颈通常在数据层、消息层、模型调用、跨地域网络而非单语言本身。
3. 企业级能力来自架构治理（SLO、门禁、回滚、多活）而不是单点语言切换。

推荐路线：

- “热点路径 Go 化”而不是“全量重写 Go 化”。
- 保留 Java API 契约层，减少客户端与生态改造成本。
- 用消息总线与标准协议解耦语言边界。

## 2) 向量知识库升级（Milvus / Qdrant）

已实现：

- `src/travel_agent/memory/vector_store.py` 支持 `local` / `qdrant` / `milvus` 三种后端。
- 环境变量：
  - `TRAVEL_VECTOR_BACKEND=local|qdrant|milvus`
  - `TRAVEL_VECTOR_STRICT=true|false`
  - `TRAVEL_VECTOR_COLLECTION`
  - `QDRANT_URL`
  - `MILVUS_HOST` / `MILVUS_PORT`

设计说明：

- local 用于教学和离线演示。
- qdrant/milvus 用于生产语义检索与长期记忆。
- strict 模式可强制失败，避免“误以为已启用向量库”。

## 3) MQ 升级：默认 Pulsar

已实现：

- `src/travel_agent/events/bus.py` 新增事件总线：`LocalEventBus` + `PulsarEventBus`。
- 默认配置：`TRAVEL_EVENT_BUS=pulsar`（不可用时可降级 local）。
- 编排链路事件埋点：
  - `recommend.requested`
  - `recommend.a2a_dispatched`
  - `recommend.completed`

用途：

- 解耦异步任务（审计、画像、离线特征、异步通知）。
- 支撑跨地域事件复制和消费组扩展。
- 为多活架构提供跨区域事件分发能力。

## 4) 全球多活部署建议

### 分层多活

1. **流量层**：全球 Anycast + GeoDNS，按区域就近接入。
2. **网关层**：多区域 Gateway 集群，按租户或国家分区。
3. **运行时层**：Agent Runtime 按区域部署，优先本地依赖。
4. **数据层**：
   - 关系数据：多主谨慎，建议主从 + 区域写入归属。
   - 向量数据：按地域分片 + 跨区异步复制。
   - 消息总线：Pulsar 多集群联邦 / geo-replication。

### 稳定性要点

- 全链路幂等：`idempotencyKey` + 去重表。
- 统一追踪：`traceparent` 跨语言透传。
- 门禁发布：Canary -> Promote / Hold / Rollback。
- 失效隔离：区域级熔断与降级开关。

## 5) 里程碑（建议）

- P1（2-4周）：Pulsar 事件闭环 + Qdrant 生产可用 + 指标看板。
- P2（4-8周）：区域双活演练 + 跨区复制 + 故障回切。
- P3（8-12周）：全球多活压测、成本治理、SLO 固化。

## 6) 智能体扩展与编排升级（新增）

已实现新增业务智能体：

- `food-recommendation-agent`
- `local-event-agent`
- `loyalty-growth-agent`

目标：提升业务粘性、增加复购和二次触达能力。

编排引擎升级：

- `TRAVEL_ORCHESTRATION_ENGINE=local|langgraph|agentscope|oneagents`
- 默认值设置为 `langgraph`，以便后续平滑演进到深度图编排。
- 保持 native fallback，避免试验期破坏主链路稳定性。

## 7) Redis Cluster 升级与场景扩展（新增）

升级方向：

- 记忆存储支持 Redis Cluster (`TRAVEL_REDIS_MODE=cluster`)
- 缓存管理扩展到：热点缓存、限流、幂等、分布式锁、画像缓存

部署入口：

- `platform/deploy/docker-compose.yml` 已加入 `redis-cluster` 服务

场景脚本：

- `stress/redis_cluster_scenarios.py`

## 8) 风险声明（必须）

## 6) 风险声明（必须）

- “10B 用户 / 10M 并发”是**系统级目标**，不是单服务压测结论。
- 任何对外容量口径必须附：压测场景、参数、持续时长、回滚演练证据。

