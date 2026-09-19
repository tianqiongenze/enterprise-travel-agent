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
