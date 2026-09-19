# 测试与部署方案

## 1. 测试策略

### 单元测试

- `test_scoring.py`：评分函数正确性
- `test_orchestrator.py`：端到端推荐、A2A日志、MCP审计
- `test_api_contract.py`：API模块可导入契约
- `test_agent_expansion.py`：新增业务智能体与工具注册验证
- `test_orchestration_engine_modes.py`：引擎模式切换与事件埋点验证
- `test_redis_cluster_mode.py`：Redis Cluster模式初始化验证
- `test_cache_manager.py`：Redis扩展缓存场景（行程快照/热门计数/最近搜索）验证

### 验证命令

```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
python3 -m src.travel_agent.run_demo
```

## 2. Docker Compose（开发环境）

使用 `deploy/docker-compose.yml` 启动 API 服务。

新增：`redis-cluster` 服务用于本地集群模式联调。

### 2.1 一键脚本离线包模式（Windows/macOS/Linux）

离线第 3 层（预构建镜像）已接入：

- `techgroup-enterprise-travel-gateway` 使用 `enterprise-travel-agent-gateway:local`
- `techgroup-enterprise-travel-web` 使用 `enterprise-travel-agent-web:local`
- `travel-agent-api` 使用 `enterprise-travel-agent-api:local`
- compose 启动阶段不再执行在线 `mvn/npm/pip install`

- 在线机器先准备离线包（拉取镜像并产出签名清单）：

```bash
python3 -u platform/deploy/scripts/one_click_stack.py \
  --project-root . \
  --package-mode prepare \
  --offline-bundle-dir platform/deploy/offline_bundle \
  --bundle-tool-targets windows-amd64,linux-amd64,darwin-amd64,darwin-arm64
```

- 可选：把离线 Docker 安装器一并打包（BYO 文件路径）

```bash
python3 -u platform/deploy/scripts/one_click_stack.py \
  --project-root . \
  --package-mode prepare \
  --offline-bundle-dir platform/deploy/offline_bundle \
  --bundle-docker-installer-windows "D:/installers/DockerDesktopInstaller.exe" \
  --bundle-docker-installer-linux "/tmp/docker-linux-installer.tgz" \
  --bundle-docker-installer-macos "/tmp/Docker.dmg"
```

- 将 `platform/deploy/offline_bundle/` 拷贝到目标机器后执行离线启动：

```bash
python3 -u platform/deploy/scripts/one_click_stack.py \
  --project-root . \
  --package-mode offline \
  --offline-bundle-dir platform/deploy/offline_bundle \
  --offline-tool-install-dir var/offline_tools/bin \
  --offline-strict
```

- 平台包装脚本同样支持环境变量：
  - `TRAVEL_PACKAGE_MODE=online|prepare|offline`
  - `TRAVEL_OFFLINE_BUNDLE_DIR=platform/deploy/offline_bundle`
  - `TRAVEL_ARTIFACT_MANIFEST=artifacts.manifest.json`
  - `TRAVEL_OFFLINE_STRICT=true|false`
  - `TRAVEL_OFFLINE_TOOL_INSTALL_DIR=var/offline_tools/bin`
  - `TRAVEL_BUNDLE_TOOL_TARGETS=windows-amd64,linux-amd64,darwin-amd64,darwin-arm64`

说明：

- 离线模式会自动把 `kubectl/kind` 从 bundle 安装到 `TRAVEL_OFFLINE_TOOL_INSTALL_DIR` 并注入当前 PATH。
- Docker daemon 仍依赖宿主机能力。若 `docker` 缺失，Windows 会尝试使用离线包中的 `docker-desktop-installer.exe` 静默安装；Linux/macOS 建议提前通过企业镜像源或 BYO 安装器完成 Docker 引擎安装。

Rancher Desktop（Windows）K8s 模式：

- 需要管理员权限安装（`choco install rancher-desktop -y` 或 MSI 安装）。
- 启动 Rancher Desktop 并启用 Kubernetes 后，执行：

```powershell
powershell -ExecutionPolicy Bypass -File platform/deploy/scripts/one_click_stack_windows.ps1 -K8sProvider rancher-desktop
```

## 3. Kubernetes（生产示例）

- Deployment：2副本
- Service：ClusterIP
- ConfigMap：运行参数（默认城市、日志级别）

## 4. 非功能性要求覆盖

- 可扩展性：无状态 API + 可横向扩展
- 可观测性：MCP 调用审计 + A2A 消息日志
- 可维护性：模块化分层 + 可替换工具层
- 稳定性：推荐逻辑与数据层解耦，支持降级

## 5. 注册中心说明

- `TRAVEL_REGISTRY=nacos-real`：默认使用真实 Nacos
- `TRAVEL_REGISTRY=etcd-real`：默认可切换真实 Etcd
- `TRAVEL_REGISTRY=nacos`：使用 Nacos 风格注册实现（内存模拟）
- `TRAVEL_REGISTRY=etcd`：使用 Etcd 风格注册实现（内存模拟）

真实集群模式：

- `TRAVEL_REGISTRY=nacos-real`：接入 Nacos OpenAPI（`NACOS_SERVER_ADDR` 等）
- `TRAVEL_REGISTRY=etcd-real`：接入 Etcd 客户端（`ETCD_HOST/ETCD_PORT`）

可选严格模式：

- `TRAVEL_REGISTRY_FAIL_FAST=true`：真实注册中心不可用时启动失败（生产推荐）
- `TRAVEL_REGISTRY_FAIL_FAST=false`：自动降级本地注册（开发推荐）

两者均提供：

- Agent 服务注册/发现
- MCP 工具目录注册

## 5.1 生产依赖（Python）

- `requests`（Nacos OpenAPI）
- `etcd3`（Etcd v3 客户端，当前实现沿用）

Etcd 客户端迁移（新旧兼容双栈）：

- `requirements-etcd-legacy.txt`：legacy 客户端（python-etcd3）
- `requirements-etcd-new.txt`：new 客户端（etcd3-py）
- 环境变量：`TRAVEL_ETCD_CLIENT_MODE=legacy|new|auto`
- 推荐迁移路径：legacy 全量运行 -> canary 切换 new -> 全量切换 -> 下线 legacy

Python 运行环境升级：

- 基线版本：Python 3.12
- FastAPI: 0.135.2
- Uvicorn: 0.42.0
- Pydantic: 2.12.0
- Requests: 2.32.5
- Aiohttp: 3.13.3
- urllib3: 2.6.0
- redis-py: 7.4.0

可选编排框架（按需安装）：

- `requirements-orchestration-optional.txt`
  - `langgraph`
  - `agentscope`
  - `oneagents`（按实际发行版选择）

## 5.3 记忆存储（Memory）

- 默认：内存存储（无需额外依赖）
- Redis：设置 `TRAVEL_MEMORY_BACKEND=redis` 与 `REDIS_URL`
- RocksDB：设置 `TRAVEL_MEMORY_BACKEND=rocksdb` 与 `TRAVEL_ROCKSDB_PATH`（显式依赖）
- Vector：设置 `TRAVEL_MEMORY_BACKEND=vector`（轻量语义检索）
- Runtime API 需 `tenantId/userId/conversationId` 作为会话隔离键

向量后端扩展（生产建议）：

- `TRAVEL_VECTOR_BACKEND=local|qdrant|milvus|faiss`
- `TRAVEL_VECTOR_STRICT=true|false`
- Qdrant: `QDRANT_URL`, `TRAVEL_VECTOR_COLLECTION`
- Milvus: `MILVUS_HOST`, `MILVUS_PORT`, `TRAVEL_VECTOR_COLLECTION`
- Faiss: 安装 `requirements-rag-optional.txt` 后启用本地高性能 ANN 检索

严格语义（生产推荐）：

- 当显式设置 `redis/rocksdb/vector` 时，不做静默降级
- 配置缺失或依赖缺失时直接报错，避免“误以为已启用”

Redis Cluster 推荐配置：

- `TRAVEL_REDIS_MODE=cluster`
- `TRAVEL_REDIS_URL=redis://<cluster-entry>:7000`
- `TRAVEL_REDIS_MAX_CONNECTIONS=800`

缓存场景扩展（已实现）：

- 热点攻略缓存
- 用户限流
- 幂等去重
- 分布式锁
- 用户画像缓存
- 行程快照缓存
- 热门城市计数
- 最近搜索历史

会员分级与权限控制：

- 请求字段：`membershipTier=basic|silver|gold|platinum`
- 不同等级限制可用工具与可用编排引擎。

会员分布式存储与缓存：

- `TRAVEL_MEMBERSHIP_REDIS_URL`

防刷、防重与熔断：

- `TRAVEL_RATE_LIMIT_PER_MINUTE`, `TRAVEL_RATE_LIMIT_WINDOW_SEC`
- `TRAVEL_IDEMPOTENCY_TTL_SEC`
- `TRAVEL_CIRCUIT_FAIL_THRESHOLD`, `TRAVEL_CIRCUIT_COOLDOWN_SEC`

## 5.2 生产依赖（Java）

- Spring Boot `3.5.12`
- Spring AI `1.1.3`
- Spring AI Alibaba `1.1.2.2`

## 6. A2A 协议测试建议

```bash
curl -X POST http://localhost:8000/a2a/send \
  -H 'Content-Type: application/json' \
  -d '{"sender":"manager-agent","receiver":"trip-planner-agent","topic":"demo","payload":{"k":"v"}}'

curl http://localhost:8000/a2a/inbox/trip-planner-agent
```

## 7. 分布式压测与上线

- 压测方案：`stress/distributed-plan.md`
- 100万记录人工测试运行手册：`docs/manual-1m-record-testing.md`
- CI/CD 流水线：`.github/workflows/ci-cd.yml`
- 灰度发布：`deploy/k8s/canary-rollout.md`

可插拔编排引擎（A2A/MCP/Skills/Harness增强）：

- `TRAVEL_ORCHESTRATION_ENGINE=local|langgraph|agentscope|oneagents`
- 默认值为 `langgraph`，其余模式按环境变量覆盖。
- 可选影子观测：`TRAVEL_ORCHESTRATION_SHADOW_ENGINE=agentscope|oneagents`
- `local/native` 模式会自动切换到 `TRAVEL_ORCHESTRATION_FALLBACK_ENGINE` 指定的框架引擎。
- `TRAVEL_ORCHESTRATION_STRICT=true` 时，未知模式将直接报错。

A2A 分布式传输：

- `TRAVEL_A2A_TRANSPORT=redis`
- `TRAVEL_A2A_REDIS_URL=redis://<cluster-entry>:7000`
- `TRAVEL_A2A_STREAM_GROUP=a2a-consumers`
- `TRAVEL_A2A_PENDING_RETRY_IDLE_MS=10000`
- 测试模式：`TRAVEL_A2A_TRANSPORT=mock-distributed`

A2A 运维核验：

- `python deploy/scripts/export_a2a_stream_metrics.py`
- `python stress/a2a_audit_replay_check.py --file var/events/a2a_audit_events.jsonl`
- `deploy/k8s/a2a-metrics-cronjob.yaml`
- `deploy/monitoring/grafana-dashboard-a2a-stream-pulsar.json`

跨语言高性能实践（Redis/Pulsar）：

- Python：Redis Streams 使用批量 ACK（pipeline）+ pending reclaim；Pulsar consumer 使用 worker 并行与有界队列。
- Java（Gateway）：Lettuce async cache + short-timeout fallback；Pulsar producer 使用 batching/maxPending/compression。
- Go（Policy）：幂等缓存与异步日志队列降低评估链路阻塞；建议在具备网络依赖时接入 go-redis cluster/ring 与 Pulsar async producer。

## 7.1 Pulsar 事件流水线（P2）

- 默认事件总线：`TRAVEL_EVENT_BUS=pulsar`
- 服务地址：`PULSAR_SERVICE_URL=pulsar://<broker>:6650`
- 消费者运行：

```bash
python3 scripts/run_event_consumers.py --max-messages 100
```

产物（默认输出目录 `var/events/`）：

- `audit_events.jsonl`
- `profile_updates.jsonl`
- `notifications.jsonl`

## 7.2 容量与成本模型（P2）

```bash
python3 stress/capacity_cost_model.py --peak-connected 1000000 --active-ratio 0.1
```

输出：

- `stress/capacity_cost_report.json`
- `stress/capacity_cost_report.md`

## 8. Etcd 迁移演练与 Canary 对比

- 演练脚本：`stress/etcd_migration_drill.py`
- 报告模板：`docs/canary-etcd-migration-report-template.md`
- 自动输出：
  - `stress/etcd_migration_compare.json`
  - `stress/etcd_canary_report.md`

## 9. Redis Cluster 场景演练

```bash
python3 stress/redis_cluster_scenarios.py
```

输出示例：

- 热点缓存命中验证
- 限流计数结果
- 幂等键重复提交结果
- 分布式锁加解锁结果
