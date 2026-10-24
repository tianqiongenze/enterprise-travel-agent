# Staging 集群复测 Runbook（kind 实测）

> Gap5 交付物。执行载体：GitHub Actions（`staging-retest-kind` workflow，runner 网络/磁盘不受本机限制）。
> 本机 Rancher Desktop/kind 仍可复现，步骤完全一致；本地执行需预留 ≥6GB 磁盘与 ≥4GB 内存。

## 1. 目的与范围

在 kind 集群上完整验证 staging overlay 的真实可部署性与运行时行为：

- 渲染并应用 `platform/deploy/k8s/kustomize/overlays/staging`（1110 行左右，含 base 全量资源）。
- 等待 4 个 Deployment + 1 个 StatefulSet 全部 rollout 完成（`kubectl rollout status`）。
- 以真实 HTTP 流量执行冒烟 + canary 双通道压测（legacy API vs go-ranker）。
- 用 `canary_gate.py` 依据 staging 阈值给出 promote/rollback 决策。

## 2. 环境约定

| 组件 | 版本/说明 |
|------|-----------|
| kind | v0.29.0（cluster name: `travel-staging`） |
| kustomize | v5.5.0 standalone，`--load-restrictor LoadRestrictionsNone` |
| 镜像 | 全部本地构建后 `kind load docker-image` 注入，不依赖外部 registry |
| Go 构建 | `GOPROXY=https://goproxy.cn,direct`；构建目标为包 `.`（非 `./main.go`） |
| 监控 CRD | 预装 prometheus-operator v0.76.2 的 ServiceMonitor/PodMonitor/PrometheusRule CRD |
| TLS Secret | CI 内以自签证书替换 `REPLACE_WITH_BASE64_CERT/KEY` 占位符（占位符非法 base64，apply 必失败；证书不入库） |
| CronJob | `travel-agent-a2a-metrics-exporter` 冒烟窗口内 suspend（依赖外部 etcd，避免噪音） |
| 容量适配 | staging overlay 携带生产级 HPA（api minReplicas=24/max=600，ranker min=4）与生产级资源请求（api 1000m/1Gi）；单节点 kind（allocatable ≈2 CPU）调度不下。冒烟窗口内删除全部 HPA、每服务钉 1 副本、api 请求降为 500m/512Mi。overlay 保持生产形态不变，此适配仅存在于执行环境 |

## 3. 流量与证据口径（禁止伪造，全部为集群真实测量）

- **legacy 通道**：`POST /recommend`（travel-agent-api，Python legacy ranker，`TRAVEL_RANKER_BACKEND=go` + shadow=true 时内部同时调用 go-ranker）
- **new 通道**：`POST /v1/score/hotel`（go-ranker，gin，`{price, rating, duration, tags, budget, weights}`）
- 每通道顺序 120 次请求，success = HTTP 200，延迟按最近邻秩取 p95/p99
- `success_rate_gap = |legacy_sr - new_sr|`，`p95/p99_drift = (new - legacy) / legacy`
- 阈值（与 staging overlay ConfigMap 一致）：gap ≤ 0.03，p95 drift ≤ 0.08，p99 drift ≤ 0.10
- 决策：`canary_gate.py --report canary_report.json --out canary_gate_decision.json`，action 必须为 `promote`

## 4. 证据清单（Actions artifact: `staging-retest-evidence`）

| 文件 | 内容 |
|------|------|
| `staging-rendered.yaml` | kustomize 渲染结果（已替换 TLS） |
| `canary_report.json` | 双通道真实测量 summary + 原始延迟数组 |
| `canary_gate_decision.json` | gate 决策（action/reasons/thresholds） |
| `canary_gate_metrics.prom` | 决策对应的 Prometheus 指标 |
| `api_metrics.txt` | travel-agent-api `/metrics` 抓取 |
| `pf-api.log` / `pf-ranker.log` | port-forward 日志 |
| `cluster_state.txt` | get all / events / describe nodes |
| `pods.txt` | Pod 名称/阶段/IP |

## 5. 触发方式

```bash
# push 即触发（branch: gap/5-staging-retest 或 main），或手动：
gh workflow run staging-retest-kind   # 需 gh CLI；或 GitHub UI → Actions → staging-retest-kind → Run workflow
```

## 6. 本机复现（可选，资源受限时以 CI 为准）

1. 启动 Rancher Desktop（容器运行时 dockerd/moby）。
2. `kind create cluster --name travel-staging`。
3. 构建 5 个镜像（API 用 `platform/deploy/docker/Dockerfile.travel-agent-api`，4 个 Go 服务用各自 Dockerfile）。
4. `kind load docker-image ... --name travel-staging` ×5。
5. 按 §2 约定渲染+修补 TLS + apply + suspend cronjob。
6. `kubectl rollout status` 逐个等待。
7. 两个终端各起 `kubectl port-forward`（18000→8000、18090→8090），运行 §3 同口径压测脚本。
8. `python platform/deploy/scripts/canary_gate.py ...` 出决策。
9. 结束后 `kind delete cluster --name travel-staging` 释放资源。
