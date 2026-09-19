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
