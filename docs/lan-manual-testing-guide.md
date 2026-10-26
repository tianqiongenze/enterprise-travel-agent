# 局域网人工测试操作指南（第四轮交付物）

- 适用对象：局域网内的测试人员、评审专家、文旅业务方（无需任何开发环境）
- 被测环境：`10.167.2.175 / 10.167.2.176` K8s 集群 `travel-prod` 命名空间（第四轮重构后版本，镜像 `:fourth6`）
- 前置条件：您的电脑与 10.167.2.x 网段互通（能 ping 通 10.167.2.175 即可）；无需 SSH
- 预计用时：冒烟 5 分钟；完整用例 40 分钟
- 访问入口（NodePort，双节点等价，任选其一）：

| 服务 | 入口 A（master 节点） | 入口 B（worker 节点） | 说明 |
|---|---|---|---|
| API 全家福（REST+GraphQL+metrics） | `http://10.167.2.175:30181` | `http://10.167.2.176:30181` | 浏览器/curl 均可 |
| go-ranker（Go 排序服务） | `http://10.167.2.175:30191` | `http://10.167.2.176:30191` | 直连验证 |

> 环境变量 `BASE=http://10.167.2.175:30181`，下文统一用 `$BASE` 指代。Windows PowerShell 用户请先执行 `$BASE = "http://10.167.2.175:30181"`；Git Bash/Linux 用户 `export BASE=...`。

---

## 一、5 分钟冒烟（必做）

### 1.1 健康探针（浏览器直接打开或 curl）

```bash
curl $BASE/health          # 期望：{"status":"ok"}
curl $BASE/graphql/health  # 期望：{"status":"graphql-schema-loaded"}
curl -o /dev/null -s -w "%{http_code}\n" $BASE/metrics   # 期望：200
```

✅ 通过标准：三个都是 200，JSON 与期望一致。

### 1.2 GraphiQL 可视化测试（推荐！浏览器即开即用）

直接用浏览器打开：**`http://10.167.2.175:30181/graphql/`**（注意结尾有 `/`）

这是 strawberry 自带的交互式查询界面（GraphiQL）。左侧粘贴以下查询，点击 ▶ 执行：

```graphql
query {
  recommend(payload: { city: "北京", days: 3 }) {
    city
    days
    hotels { name price score }
    transports { name price duration }
    itinerary { day summary }
    engagements { title }
  }
  health
}
```

**期望结果**（2026-10-27 实测真实数据）：

```json
{
  "data": {
    "recommend": {
      "city": "北京", "days": 3,
      "hotels": [
        {"name": "北京中心商务酒店", "price": 780.0, "score": 1.147},
        {"name": "北京家庭轻居酒店", "price": 520.0, "score": 1.125}
      ],
      "transports": [
        {"name": "民航经济舱", "price": 860.0, "duration": 0.0},
        {"name": "高铁二等座", "price": 560.0, "duration": 0.0}
      ],
      "itinerary": [ {"day": "Day 1", ...}, {"day": "Day 2", ...}, {"day": "Day 3", ...} ],
      "engagements": [ ... 12 项 ... ]
    },
    "health": "ok"
  }
}
```

换城市再试：把 `city` 换成 `"上海"`、`"杭州"`、`"成都"`、`"西安"`，观察酒店/交通数据变化（不同城市数据集不同）。

### 1.3 REST 接口冒烟

```bash
cat > /tmp/rec.json <<'EOF'
{"city":"北京","days":3}
EOF
curl -s -X POST $BASE/recommend -H "Content-Type: application/json" --data-binary @/tmp/rec.json | python -m json.tool
```

（无 python 时去掉 `| python -m json.tool` 直接看原文）

✅ 通过标准：HTTP 200，包含 `city/days/hotel_options/transport_options/itinerary/engagement_recommendations` 六个字段。

---

## 二、REST 全接口用例（约 15 分钟）

| # | 用例 | 命令 | 期望 |
|---|------|------|------|
| R1 | 空参数默认行程 | `curl -s -X POST $BASE/recommend -H "Content-Type: application/json" -d "{}"` | 200，默认 北京/3天 |
| R2 | 会员等级传递 | `-d "{\"city\":\"杭州\",\"membershipTier\":\"gold\"}"` | 200，响应结构与 R1 一致 |
| R3 | 偏好标签 | `-d "{\"city\":\"成都\",\"preferences\":[\"亲子\",\"美食\"]}"` | 200 |
| R4 | 多日行程 | `-d "{\"city\":\"西安\",\"days\":5}"` | 200，itinerary 有 5 天 |
| R5 | 错误类型拒绝 | `-d "{\"days\":\"abc\"}"` | 422（FastAPI 参数校验） |
| R6 | /health.grpc 存在性 | `curl $BASE/health/grpc` | 200 或 404 均可接受（gRPC 面开关默认关） |
| R7 | metrics 计数增长 | 连续两次 `curl $BASE/metrics \| grep recommend` | 第二次 `travel_runtime_requests_total{...route="/recommend"}` 数值变大 |

> Windows PowerShell 多行 JSON 建议用文件方式：`curl.exe -X POST $BASE/recommend -H "Content-Type: application/json" --data-binary @rec.json`（注意用 `curl.exe` 而不是 `curl` 别名）。

---

## 三、GraphQL 深度用例（GraphiQL 里操作，约 10 分钟）

### 3.1 变量化查询（生产推荐姿势）

```graphql
query Trip($city: String, $days: Int) {
  recommend(payload: { city: $city, days: $days }) {
    city days
    hotels { name price score }
  }
}
```

变量面板（GraphiQL 左下角）填：`{"city": "三亚", "days": 4}`

### 3.2 防雪崩守卫演示（架构亮点，必测）

**深度守卫**（TRAVEL_GRAPHQL_MAX_DEPTH=7）：粘贴并执行——

```graphql
query {
  recommend(payload: { city: "北京" }) {
    hotels { name x1 { x2 { x3 { x4 { x5 { x6 { x7 { x8 } } } } } } } }
  }
}
```

期望：`errors` 中报字段不存在或深度超限（`data: null`）——恶意深嵌套在进入业务逻辑前被拦截。

**成本守卫**（TRAVEL_GRAPHQL_MAX_COST=1000）：构造一个放大 1000 倍的列表查询（把 hotels/transports/itinerary/engagements 各层重复嵌套多级）执行，期望被 `query cost ... exceeds limit` 拒绝。

**错误查询**（schema 校验）：

```graphql
query { hello }   # 不存在的字段
```

期望：`Cannot query field 'hello' on type 'Query'`——schema 是强契约（SDD 单一事实源在 `data-contracts/graphql/schema.graphql`）。

### 3.3 REST/GraphQL 契约一致性抽查

同一个城市分别用 REST（§1.3）和 GraphQL（§1.2）查询，比对：`city`、`days`、酒店名称列表、价格——**两边必须完全一致**（第四轮修复的契约对齐点）。

---

## 四、观测面人工读数（10 分钟）

打开 `http://10.167.2.175:30181/metrics`（或 curl），按 Ctrl+F 查找以下指标：

| 指标 | 含义 | 人工验证方法 |
|---|---|---|
| `travel_runtime_requests_total{route=...,code=...}` | 各路由请求计数 | 连续点几次 /health 后刷新，计数 +N |
| `travel_runtime_request_latency_seconds_count/sum` | 延迟直方图 | sum÷count ≈ 平均延迟，人工比对体感 |
| `travel_cache_hit_rate` / `travel_cache_l1_hits_total` | 多级缓存命中率 | **首次调用 miss、TTL 5s 内重复调用命中**：快速连续查同一城市两次，l1_hits 增加 |
| `travel_runtime_rejects_total{reason=...}` | 限流/熔断拒绝数 | 压测时观察增长 |

**缓存命中率小实验**（30 秒）：对同一城市快速执行 /recommend 五次（5 秒内），然后看 `travel_cache_l1_hits_total`——第 2~5 次应命中 L1。超过 5 秒后再查会 miss（TTL 过期回源），这是设计行为。

---

## 五、go-ranker 直连测试（5 分钟）

```bash
curl http://10.167.2.175:30191/health
# 期望 {"status":"ok"}

cat > /tmp/rank.json <<'EOF'
{"price":860.0,"rating":4.6,"duration":2.5,"tags":["wifi"],"budget":1200.0,"weights":{"price":0.4,"rating":0.4,"duration":0.2}}
EOF
curl -s -X POST http://10.167.2.175:30191/v1/score/hotel -H "Content-Type: application/json" --data-binary @/tmp/rank.json
# 实测期望：{"score":1.13390698}

# 交通打分
curl -s -X POST http://10.167.2.175:30191/v1/score/transport -H "Content-Type: application/json" --data-binary @/tmp/rank.json
# 批量
curl -s -X POST http://10.167.2.175:30191/v1/score/hotel/batch -H "Content-Type: application/json" -d '{"items":[{"price":780,"rating":4.5,"tags":["wifi"],"budget":1000,"weights":{}},{"price":520,"rating":4.2,"tags":[],"budget":1000,"weights":{}}]}'
```

✅ 通过标准：score 数值稳定复现（同输入同输出，纯函数），与 GraphQL 面返回的 score 一致。

---

## 六、进阶：并发与弹性人工观察（15 分钟，可选）

### 6.1 简易并发（PowerShell 或 bash 循环）

```bash
for i in $(seq 1 50); do curl -s -o /dev/null -w "%{http_code} %{time_total}s\n" -X POST $BASE/recommend -H "Content-Type: application/json" --data-binary @/tmp/rec.json & done; wait
```

观察：全部 200；时间大多在 0.1~2s；刷新 `/metrics` 看 `travel_runtime_requests_total` 涨了 50。

### 6.2 HPA 自动扩容观察（需 SSH，给运维/评审演示）

```bash
ssh root@10.167.2.175 "kubectl -n travel-prod get hpa travel-agent-api-hpa -w"
```

另一窗口跑 §6.1 的大循环（或 K6），观察 `REPLICAS` 从 3 自动上涨（第四轮实测 200VU 时 3→11），负载回落后缩容。

### 6.3 K6/Locust 复跑（运维向，脚本已入库）

```bash
# K6（50VU 稳态轮，期望全绿：P95<300ms、错误率 0）
ssh root@10.167.2.175 "kubectl -n travel-prod delete job k6-fourth-round --ignore-not-found; kubectl apply -f /root/fourth/k6job.yaml"
ssh root@10.167.2.175 "sleep 260; kubectl -n travel-prod logs job/k6-fourth-round --tail=40"

# Locust Web UI（浏览器打开可视界面）
ssh root@10.167.2.175 "kubectl -n travel-prod port-forward --address 0.0.0.0 deploy/locust-fourth-master 8089:8089"
# 局域网浏览器打开 http://10.167.2.175:8089 设置用户数后 Start
```

> 基线对照：50VU → 252 req/s / P95 262ms / 0%；400 用户业务仿真 → 31,793 请求 0 失败（详见 `stress/fourth_round_test_report.md`）。

---

## 七、常见问题排查

| 现象 | 原因 | 处理 |
|---|---|---|
| 浏览器打开 `/graphql` 变成空白页/下载文件 | 少了结尾斜杠，被 307 重定向 | 用 **`/graphql/`**（带斜杠），或继续用 POST 方式 |
| `There was an error parsing the body` | Windows curl 引号转义问题 | 用 `--data-binary @文件.json` 方式（见 §1.3） |
| 偶发 3~7 秒慢请求 | 冷启动 pod 首次加载模型/数据（L1 未热） | 连续请求 2 次后恢复毫秒级；属已知行为 |
| NodePort 不通 | 不在同网段/防火墙 | `ping 10.167.2.175` 验证；联系管理员放行 30181/30191 |
| metrics 打不开 | 少了 `$BASE` 前缀或端口写错 | 全文只有 30181（API）与 30191（ranker）两个入口 |
| recommend 偶发 500 | 触发了令牌桶限流（默认 600/分钟） | 查看 `/metrics` 里 `travel_runtime_rejects_total`；间隔后自动恢复 |

## 八、测试记录表（打印用）

| 用例 | 结果(✓/✗) | 实测值 | 测试人/时间 |
|---|---|---|---|
| §1.1 三探针 200 | | | |
| §1.2 GraphiQL 北京推荐 | | hotels=2? | |
| §1.3 REST 六字段契约 | | | |
| §2 R5 参数校验 422 | | | |
| §2 R7 metrics 计数增长 | | | |
| §3.2 深度守卫拒绝 | | | |
| §3.3 双面契约一致 | | | |
| §四 缓存 L1 命中 | | l1_hits=? | |
| §五 ranker score 复现 | | score=? | |
| §6.1 50 并发全 200 | | | |

## 九、环境备注（运维）

- 入口服务为 `travel-prod/travel-agent-api-lan`（NodePort 30181）与 `go-ranker-lan`（30191），清单随仓库 `platform/deploy/k8s/`（第四轮追加），删除即回收端口，不影响集群内 ClusterIP 通信。
- 后端 pod 当前 3 副本（HPA 3→30，CPU 65%）；压测前建议确认 `kubectl -n travel-prod get pods` 全部 Running。
- 本指南所有"期望结果"均为 2026-10-27 在该集群实测采集的真实值。
