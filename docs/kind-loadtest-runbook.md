# 本机 kind 集群压测与故障演练 Runbook（Phase 3）

> 目的：以**真实集群证据**替代本地自签推算。执行后产出 `stress/` 下的 k6/Locust
> 原始结果与签名故障演练证据；local 环境证据**不被** go-live 门禁的
> staging/prod 档位接受（这是有意的治理设计）。

## 0. 前置条件

| 工具 | 版本建议 | 安装 |
|------|---------|------|
| Docker Desktop | ≥ 4.30 | Windows: WSL2 后端 |
| kind | ≥ 0.23 | `go install sigs.k8s.io/kind@latest` 或 scoop |
| kubectl | 与集群匹配 | `winget install kubectl` |
| k6（推荐）| ≥ 0.50 | `winget install k6 --source winget` |
| Locust（备选）| latest | `pip install locust` |

## 1. 一键执行

```bash
export TRAVEL_EVIDENCE_SIGNING_KEY="replace-with-strong-key"
bash platform/deploy/scripts/run_kind_loadtest.sh --concurrency 50 --duration 60
```

脚本做五件事：
1. 构建 API/Gateway/Web 本地镜像；
2. 创建/复用 `travel-agent` kind 集群并注入镜像；
3. 应用 `platform/deploy/k8s/local` overlay 并等待 rollout；
4. 运行压测（k6 → Locust → 内置 load_test 降级），输出原始 JSON；
5. 三轮 Pod-Kill 故障演练（删除 API Pod → 等 rollout 恢复），调用
   `fault_drill_evidence_ingest.py` 生成 HMAC 签名证据并关联压测结果。

## 2. 证据解读（防止再次「自证循环」）

- `evidenceSource=kind-cluster-drill`：本机集群实测，可用于教学与回归；
- 通过门禁需要 `--allowed-evidence-environments staging,prod`，即必须用
  同一脚本在真实 staging 集群（GitHub Actions `environment: production-deploy`
  或内网集群）重跑并改用 `--environment staging`；
- 演练判定阈值在 `fault_drill_evidence_ingest.py::_benchmark_gate`
  （p95≤1200ms、p99≤1500ms、错误率≤1%），证据不达标时 `pass=false`。

## 3. 历史证据矛盾的处理结论

`stress/locust_runtime_local_1000_stats.csv`（41949 请求 100% 失败）与
`stress/report_5k.json`（100% 成功）并存：前者为直连 Runtime 未启动时的
失败采样（status=0 = 连接拒绝），后者为 Runtime 本机运行时采样。两者均
**不构成** 生产容量证据；生产级证据以本 runbook 的集群执行结果为准。

## 4. Chaos Mesh（可选进阶）

Pod-Kill 覆盖「实例失效」场景；网络分区 / CPU 满载等场景建议安装
Chaos Mesh 后使用其 Workflow 注入（`stress/` 已支持 chaosmesh schema 的
证据导入）。kind 单机集群内存有限，建议 ≥16GB 内存主机再跑。

## 5. 实测记录（2026-09-19，Rancher Desktop + kind）

### 5.1 环境恢复
- 原 Rancher Desktop 处于半卸载状态（WSL 发行版 ext4.vhdx 缺失、应用本体不在）：
  注销失效发行版后以 v1.24.0 MSI 静默重装（`MSIINSTALLPERUSER=1 ALLUSERS=2` 免管理员）。
- 首次构建因 **C 盘空间耗尽（3.7GB）** 触发 containerd 元数据 I/O 错误：清理 pip/npm
  缓存与安装包（+3.2GB）并重启 RD 虚机后恢复。kind 节点容器跨虚机重启自动恢复，
  集群未丢失（kind restart=unless-stopped）。
- Docker Hub 被墙：全部基础镜像经 `docker.m.daocloud.io` 拉取后 retag。

### 5.2 实测发现并修复的三个构建/启动级 bug（此前 CI 均未暴露）
1. **依赖死锁**：grpcio==1.76 与 pymilvus 2.5.4（grpcio<=1.67.1）、qdrant-client 的
   grpcio-tools（protobuf<7）三者互相矛盾 → `grpcio==1.84.0 + pymilvus==3.0.2 +
   protobuf==7.36.2`（与 gRPC stub gencode 对齐）。
2. **etcd3 无法构建**：setup.py 依赖 setuptools>=81 已移除的 `pkg_resources` →
   从镜像构建中移除 legacy etcd 客户端（保留文件供手动演练）。
3. **Nacos 注册崩溃**：`_parse_endpoint` 无法解析带路径的 endpoint
   （`http://host:8000/agent/manager`）；且注册中心不可达时直接 CrashLoop →
   解析改用 urlparse；register 失败时按 `TRAVEL_REGISTRY_FAIL_FAST` 语义降级本地注册。

### 5.3 压测结果（kind 单节点，2 副本，50 并发 × 3000 请求）
| 指标 | 数值 |
|------|------|
| 成功率 | 87.53%（2626/3000） |
| 平均延迟 | 501ms |
| p95 / p99 | 1305ms / 1668ms |

- 报告：`stress/report_kind.json`；签名证据：`stress/multi_region_fault_drill_report_kind.json`（signed=true，**pass=false**——p95 超 1200ms 演练门槛、成功率低于 99%，门禁如实拒绝）。
- 374 个 status=0 为连接层错误（客户端超时为 8s，非超时所致），成因待查（疑似 kind
  单机网络抖动/uvicorn 并发积压），列入后续工作。

### 5.4 Pod-Kill 混沌演练
3 轮删除全部 API Pod，rollout 恢复 **3/3 通过，合计 13 秒**。

### 5.5 结论与后续
- 首个真实集群证据已产生：功能链路在集群内可用、故障自愈有效；
- 容量与 SLO 未达标（符合"本机单节点"预期）；staging 档证据需在真实多节点集群
  重跑本脚本（`--environment staging`）；
- 后续：① 查明连接层错误根因；② 集群内部署 gateway 后以 k6 走全链路；
  ③ kind node 内存调至 8GB 复测。

### 5.6 项3 复测（2026-09-19，全链路经 gateway，签名证据）
在 5.3 之后完成了 gateway 集群内部署与三个降级 bug 修复（list_services/list_tools
不可达时降级缓存，见 5.2.3），并按下列方式复测：

- **探针**：集群内 `deploy/travel-agent-api-local` 直连
  `http://travel-gateway.travel-local.svc.cluster.local:8080/api/v1/travel/recommend`
  （gateway 自动补 X-Trace-Id），返回 HTTP 200，响应含全部键
  `[a2aLogs, aiRationale, auditLogs, engagementRecommendations, hotelOptions,
  itinerary, traceId, transportOptions]`，hotelOptions=2 条。
- **签名压测**：`stress/load_test_gateway.py` 以 ConfigMap 注入 + 本地镜像
  `enterprise-travel-agent-api:local` 以 Job 形式在集群内执行
  （kind 无镜像拉取网络，python:3.12-slim 会 ImagePullBackOff），报告直接
  `--out /dev/stdout` 打入 Job 日志（`kubectl logs job/loadtest-signed`），
  避开 `kubectl cp`/exec 已完成 Pod 的导出限制。
- **结果（20 并发 × 500 请求，全链路经 gateway）**：

| 指标 | 数值 |
|------|------|
| 成功率 | **100%（500/500，error=0）** |
| 全部状态码 | 200（直方图 `{"200": 500}`） |
| 平均延迟 | 5416ms |
| p95 / p99 | 5523ms / 5648ms |

- 报告文件：`stress/report_gateway_signed_kind.json`（由 Job 日志导出）。
- 延迟抬升原因：本轮经 gateway 全链路（含 A2A/审计埋点），且 API 副本为 2，
  Agent 多步编排本身耗时 ~5s；连接层错误（5.3 的 status=0）已归零。
- 结论：项3「kind 全链路」功能与稳定性目标达成——探针 200 + 500/500 成功、
  0 错误；p95 超 1200ms 演练门槛属本机资源限制，维持"staging 档证据需在真实
  多节点集群重跑"的结论。

## 6. 真 LLM / Embedding 远端验证（项4b，2026-09-19）

本机环境 **未配置** `AI_DASHSCOPE_API_KEY`，因此运行时按设计降级：
`TRAVEL_LLM_BACKEND=auto` 时 `create_rationale_provider()` 返回
`NullLlmProvider`，`TRAVEL_EMBEDDING_BACKEND=auto` 时 embedding 回退
hash 向量——推荐链路零行为变化、零报错。真远端验证按以下步骤执行
（需可出网的环境或 CI secret）：

1. 设置密钥与后端：
   ```bash
   export AI_DASHSCOPE_API_KEY="sk-..."
   export TRAVEL_EMBEDDING_BACKEND=dashscope   # 或 auto
   export TRAVEL_EMBEDDING_DIM=1024            # text-embedding-v3 为 1024 维
   export TRAVEL_LLM_BACKEND=auto              # 有 key 即激活 DashScopeLlmProvider
   ```
2. 判定标准：
   - LLM：推荐响应中 engagement 条目出现 `reasonSource=dashscope:qwen-plus`
     且 `reason` 为非模板中文短句；LLM 超时/断网时自动回落模板理由
     （日志出现 `keeping template reasons`）且响应仍 200；
   - Embedding：`VectorMemoryStore` 的 provider_name 为
     `dashscope:text-embedding-v3`，向量维度 = 1024；维度与
     `TRAVEL_EMBEDDING_DIM` 不一致时启动即抛错（fail-fast）。
3. 覆盖情况：mock 路径已由单测覆盖——`tests/test_llm_rationale.py`
   （12 用例：provider 选择、鉴权失败、行数不足、异常降级）与
   `tests/test_embedding_providers.py`（11 用例：hash 确定性/归一化、
   后端选择、维度不匹配 fail-fast、HTTP 403）。
4. 部署注入：三个环境文件（dev/staging/prod.env）已含
   `TRAVEL_LLM_BACKEND=auto` / `TRAVEL_LLM_MODEL=qwen-plus` /
   `TRAVEL_LLM_TIMEOUT_SEC=8.0`；密钥经 K8s Secret 注入，不入库。
