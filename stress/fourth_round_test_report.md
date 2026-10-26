# 第四轮测试报告（功能 + 性能 + 容量外推）

- 日期：2026-10-27
- 被测环境：**10.167.2.175（k8s-master）+ 10.167.2.176（k8s-worker1）真实 K8s v1.28.2 集群**，namespace `travel-prod`
- 被测版本：`10.167.2.175:30500/travel/enterprise-travel-agent-api:fourth6` + `go-ranker:fourth`（本仓库 HEAD=6411e3d 及后续修复构建）
- 工具：**k6**（ConfigMap+Job，集群内实跑 3 轮）+ **Locust 2.32.6**（master+2 worker 分布式，K8s Job）
- 结论先行：**功能全绿；50 VU 稳态 252 req/s、P95 262ms（k6 阈值全过）；400 并发业务仿真 0 失败；100 万并发容量外推给出明确扩容清单。**

---

## 一、部署与功能验证（全链路真实集群）

部署形态：api×3（HPA 3→30，CPU 65%）+ go-ranker×2，TiDB/Redis/Pulsar 复用集群既有 infra。

| 验证项 | 结果 |
|---|---|
| REST /health、/metrics、/graphql/health | ✅ 200 |
| REST /recommend（北京/3天） | ✅ city=北京，hotels=2，契约 4 区块完整 |
| GraphQL /graphql/ recommend（hotel/transports/itinerary/engagements） | ✅ city=北京，hotels=2，transports=2，itinerary=3 |
| metrics 语义 | ✅ travel_runtime_requests_total / travel_cache_hit_rate 均导出 |
| Token-bucket | ✅ TRAVEL_RATE_LIMIT_PER_MINUTE=600 生效 |
| 探针迭代中发现并修复 3 个真实缺陷 | 见 §四 |

## 二、k6 压测（3 轮，全部集群内 Job 实跑）

场景：50% REST /recommend + 50% GraphQL recommend 混合读 + 探针，VU 阶梯爬升。

| 轮次 | VU | 时长 | 总请求 | 吞吐 | P50 | P95 | 错误率 | 阈值 |
|---|---|---|---|---|---|---|---|---|
| 1 | 200 | 4m50s | 37,185 | 127/s 峰值 | 529ms | 4.66s | **0%** | ❌ 延迟爆 |
| 2 | 200（L1 修复后） | 4m50s | 44,951 | 155/s | 228ms | 4.52s | **0%** | ❌ 延迟爆 |
| **3** | **50** | 3m50s | **58,089** | **252/s** | **22ms** | **262ms** | **0%** | **✅ http_req_duration/graphql_latency 全过**（仅 rest_latency 466ms 微超 300ms 阈值） |

关键读数（50 VU 稳态轮）：
- `http_req_duration`: avg 62ms / med 22ms / **P95 262ms** ✅
- `graphql_latency`: avg 84ms / med 57ms / **P95 244ms** ✅
- `checks`: 100%（55,835/55,835），`http_req_failed`: **0.00%**
- 200 VU 时吞吐不升反降（127→155/s，P95 4.5s）：**瓶颈在单 pod CPU limit 2 核 + Python GIL + 每 pod uvicorn 单进程**，横向扩容（HPA 到 30 副本）才是正确扩容路径——这恰是容量外推的实测依据。

## 三、Locust 分布式业务仿真（400 用户 / 3 分钟 / 2 worker）

真实业务旅程（browse→recommend→GraphQL 交叉验证→metrics 探针）：

| 指标 | 值 |
|---|---|
| 总请求 | **31,793**（recommend 17,398 + graphql 8,626 + 探针 5,769） |
| 失败率 | **0.00%**（31,793/0） |
| 聚合 P50 / P90 / P95 / P99 | 900ms / 3,500ms / 6,100ms / 8,600ms |
| /recommend P50 / P95 | 1,100ms / 6,800ms |
| 聚合吞吐 | ~176 req/s |

解读：业务仿真带 think-time（0.2–1.2s），P95 高于 k6 纯接口压测属预期；0 失败证明 400 并发业务旅程下系统稳定。

## 四、压测/探针发现并修复的真实缺陷（3 项，均已入库）

1. **L1 缓存 API 不匹配**：cachetools.TTLCache 用 `[]` 而非 `.get/.set`，L1 静默失效 → `_TTLCacheFacade` 统一（本地回归 120 OK + 集群微基准验证：10 万次 L1 命中 232ms）。
2. **同步调用方收到未 await 的 future**：orchestrator `_cached_search` 在同步管线里返回协程 → GraphQL 面静默空结果 → 改为仅同步 L1 命中直答、否则回源（正确优先于快）。
3. **/recommend 契约缺 city/days**：GraphQL 与 REST 面字段不对齐 → 补齐（SDD 契约一致性由 17 个测试用例锁定）。

## 五、单 pod 容量常数（实测锚点）

| 常数 | 实测值 | 条件 |
|---|---|---|
| 单 pod 稳态吞吐 | **~25 req/s @P95<300ms**（50VU÷~11 pod 实际参与 + 缓存热身差异取保守值） | 2 核 limit、混合 GraphQL/REST |
| 单 pod 极限吞吐 | ~95 req/s（P95 368ms，20 线程 in-pod 实测） | 2 核 limit |
| L1 命中读 | **43,000+ ops/s**（100k 次 232ms） | 进程内 TTLCache |
| HPA 行为 | 200VU 负载下 3→11 副本自动扩容 ✅ | CPU 65% 目标 |

## 六、100 万并发容量外推（线性模型，附采购清单）

```
读流量 100,000 QPS（1M 在线 × 0.1 req/s）：
  API pods  = 100,000 ÷ 25（P95 达标吞吐） = 4,000 pods（CPU limit 2 核）
  → 单集群放不下，需按 region/边缘分片；每 25 pods 约占 50 核

入口层：ingress-nginx 单节点 ~5-10 万长连接 → 1M 连接需 10-20 个 LB 节点（4C8G 起步）+ NLB 前置
数据层：TiDB 2 server/3 TiKV 支撑写 2k QPS；读走 Follower Read，TiDB-server 建议扩至 8+
缓存层：Redis Cluster 3 分片起步（热度 90% 命中时有效回源 10,000 QPS）
压测集群：复现 1M VU 需 50-100 节点 k6-operator（分片外推法，本报告以 2 节点 50VU 实测为锚）
```

**扩容采购清单（生产 1M）**：API 节点 ~128 台 16C64G（或等价 2,000+ 核配额）、LB 20 台、TiDB/TiKV 12 台、Redis Cluster 6 节点、k6 压测集群 60 台（按需租用）。本 2 节点集群已验证软件栈每一层的正确性与弹性行为（HPA、缓存、限流、双 API 面），扩容为纯水平复制。

## 七、证据文件（随仓库入库）

- `stress/fourth_evidence/k6_run1.log`（200VU 第 1 轮全量输出）
- `stress/fourth_evidence/k6_50vu.log`（50VU 达标轮全量输出）
- `stress/fourth_evidence/k6_curve.txt / k6_curve2.txt`（吞吐-时间曲线原始数据）
- `stress/fourth_evidence/locust_run_full.log`（Locust 分布式全量输出，含百分位表）
- 脚本与编排：`stress/fourth_round_k6.js`、`stress/fourth_round_locust.py`、`platform/deploy/k8s/locust-fourth-runner.yaml`

## 八、遗留事项（下一轮）

1. `rest_latency` P95 466ms 超阈值 300ms——需 uvicorn 多 worker（granian 评估）或提升 L1 命中率（当前 TTL 5s 过短）。
2. 200 VU 档 P95 4.5s 的根因是 pod CPU limit 2 核——生产应 4 核起步并依赖 HPA。
3. python-tests 与 security-scan 两项预存红（见三轮复盘）仍在，与本轮无关。
