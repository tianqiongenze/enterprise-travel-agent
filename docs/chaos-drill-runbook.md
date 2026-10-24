# 混沌演练 Runbook（chaos_drill.sh）

## 目的

对 Go 侧三个关键依赖（ranker 评分、registry-cache 注册表缓存、runtime 编排）做故障注入验证，确认自愈能力与降级语义，并产出可审计的证据报告。

## 脚本与产物

- 脚本：`platform/deploy/scripts/chaos_drill.sh`
- 产物：`stress/chaos_drill_report.json` 与 `stress/chaos_drill_report.md`，含 UTC 时间戳、git SHA、逐场景状态（PASS/FAIL/SKIPPED）与恢复秒数。

## 三个场景

1. **ranker-pod-kill**：`kubectl delete pod -l app=travel-ranker-go --force`，轮询 containerStatuses ready 直至恢复（最长 120s）。验证 Deployment 自愈。
2. **registry-cache-scale-zero**：`kubectl scale --replicas=0` 后等待 3s，再扩回 1。验证下游在缓存不可用时的降级路径与扩容恢复。
3. **runtime-rolling-restart**：`kubectl rollout restart deployment travel-runtime` + `rollout status --timeout=180s`。验证滚动重启期间服务不中断。

## 前置条件

- kubectl 可用且已连接目标集群（本机无集群时脚本写 SKIPPED 证据并以 0 退出，不算失败）。
- 命名空间默认 `travel`，可用 `CHAOS_NAMESPACE` 环境变量覆盖。
- 环境由 kind/staging 环境提供（见 `docs/deployment-and-testing.md`），生产环境禁止直接演练，应走 staging。

## 执行

```bash
bash platform/deploy/scripts/chaos_drill.sh
```

## 判定

- 任一场景 FAIL → overall=FAIL，需要排查恢复时间超限或扩容失败原因后重跑。
- SKIPPED 属诚实证据（无集群/kubectl），不作为演练通过。

## 本机（Windows/Git Bash）注意事项

- 无本地 kubectl 集群时脚本走 SKIP 分支，已验证可正常生成报告。
- `-race` 检测器本机不可用（缺 gcc/cgo），Go 竞态检测交由 CI（linux runner）执行 `go test -race -count=1`；本地用 `go test ./... -count=1` 验证。
