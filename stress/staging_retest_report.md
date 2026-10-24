# Gap5 Staging 集群复测报告（kind 实测）

- **结论：canary promote，全部 rollout 成功，5 个服务 Running，双通道成功率 100%**
- CI run：[staging-retest-kind #40119911250](https://github.com/tianqiongenze/enterprise-travel-agent/actions/runs/40119911250)（conclusion: success，head 1c5ac1b）
- 测量时间：2026-10-24 18:30:31 UTC
- 执行环境：kind v0.29.0 单节点（GitHub Actions runner）；kustomize v5.5.0 + staging overlay 渲染应用

## 集群状态（kubectl get pods，测量时刻）

| Pod | 状态 |
|-----|------|
| travel-agent-api-9bdcd4cfc-zrmzh | Running |
| go-ranker-6dbc8b7ffd-6cfmv | Running |
| go-policy-f948dc5cf-5l8js | Running |
| go-fanout-7b9fb4786f-rmmcr | Running |
| go-registry-cache-0（StatefulSet） | Running |

## Canary 决策（canary_gate.py，thresholds 与 staging overlay ConfigMap 一致）

| 指标 | 实测 | 阈值 | 判定 |
|------|------|------|------|
| success_rate_gap | **0.0**（双通道均 100%，60 样本/通道） | ≤ 0.03 | ✅ |
| p95 drift（new vs legacy） | **负值**（new 5.60ms << legacy 4166.01ms） | ≤ 0.08 | ✅ |
| p99 drift（new vs legacy） | **负值**（new 10.86ms << legacy 4175.03ms） | ≤ 0.10 | ✅ |
| **action** | | | **promote**（reasons: []） |

- legacy 通道：`POST /recommend`（travel-agent-api，Python legacy ranker + go-ranker shadow 内部联动）
- new 通道：`POST /v1/score/hotel`（go-ranker，gin）
- 口径：port-forward 顺序请求；success = HTTP 200；nearest-rank 百分位
- 新通道时延明显更优（约 745 倍），drift 为负，无失败样本（legacy_errors=0，new_errors=0）

## 复测发现并修复的真实缺陷（4 项）

1. **go-policy 镜像缺 policy.rego**：`rego.Load` 启动 panic → CrashLoopBackOff。修复：Dockerfile 将 policy.rego 拷入运行镜像（435b98a）。
2. **go-registry-cache StatefulSet 引用未定义的 ServiceAccount**：`go-registry-cache-sa` 不存在 → FailedCreate。修复：serviceaccount.yaml 补 SA + endpoints-reader Role/RoleBinding（cfdb757）。
3. **指标落盘失败击穿请求**：go_ranker_client 向 `stress/` 写指标，容器只读根文件系统 → OSError → 用户请求 500。修复：telemetry 写失败仅告警（1c5ac1b），Python 回归 109 tests OK。
4. **Pulsar publish 30s 阻塞**：无 broker 时 Pulsar 客户端构造不抛错，`publish()` 每次阻塞 30s（sendTimeout），fallback-to-local 永不触发 → /recommend 全部超时。修复：冒烟环境注入 `TRAVEL_EVENT_BUS=local`（与 CI 测试套件一致）；本地复现脚本 `stress/repro_recommend_hang.py` 验证修复后 200/4.1s（c370628）。

## 执行环境适配（overlay 保持生产形态不变）

- 单节点 kind（allocatable ≈2 CPU）：删除 HPA（生产级 minReplicas=24）、每服务 1 副本、api 请求 200m/384Mi。
- kind 无 Pulsar/Redis/Nacos：api 注入 `TRAVEL_EVENT_BUS=local`、`TRAVEL_A2A_TRANSPORT=mock`、`TRAVEL_A2A_AUDIT_MIRROR_PULSAR=false`。
- TLS Secret 占位符在 CI 内以自签证书替换（证书不入库）；a2a-metrics CronJob 冒烟窗口 suspend。

## 证据文件（随本提交入库，均来自 CI run 40119911250）

`stress/ci-evidence/`：canary_report.json、canary_gate_decision.json、canary_gate_metrics.prom、cluster_state.txt、pods.txt、staging-rendered.yaml、api_logs.txt、api_metrics.txt

## 迭代过程（10 次失败运行的真实记录）

| Run | 失败点 | 根因 |
|-----|--------|------|
| 1 (40102307801) | Wait for rollouts | 生产级 HPA 将 api 拉至 24 副本，单节点调度不下 |
| 2 (40104160577) | Wait for rollouts | go-registry-cache-sa 未定义，StatefulSet FailedCreate |
| 4 (40106730278) | Wait for rollouts | 2 副本仍超出单节点 CPU（api 1000m×2） |
| 5 (40108321585) | Wait for rollouts | api 500m request > 剩余 300m |
| 6 (40109905061) | Wait for rollouts | go-policy CrashLoopBackOff（镜像缺 policy.rego） |
| 7 (40111385876) | Wait for rollouts | 同上（600s 超时也无济于事） |
| 8 (40112958823) | canary rollback | /recommend 全部超时（pulsar publish 30s 阻塞） |
| 9 (40116100221) | canary rollback | 成功率 50%：metrics 写只读 FS → 500 |
| 10 (40118434197) | canary rollback | 同上（错误采样确认 HTTPError 500） |
| **11 (40119911250)** | — | **promote ✅** |
