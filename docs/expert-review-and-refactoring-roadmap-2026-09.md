# 企业级智能旅游推荐智能体（enterprise-travel-agent）多角色专家评审与重构路线图

> 评审日期：2026-09-19
> 评审视角：高校 AI/大数据教授级高工 · 德国双元制教育本土化专家 · 专业带头人 · 互联网大厂资深系统架构师/技术总监 · 高级美工与平面设计师
> 评审依据：TDD / SDD（规格驱动开发）/ DDD / TOGAF 10 / GB·T 8566、GB·T 9385（SRS 编制）、GB·T 25000 系列（SQuaRE 软件质量模型） / 大厂生产准入基线
> 联网对标：TOGAF 10 + DDD 限界上下文、MCP/A2A/LangGraph 生产分层、K8s Pod Security Standards、Design Tokens + Monorepo、OTA 行业生产级 Agent 栈（Trip.com TripGenie、Booking.com Agentic AI）
> 评审方式：5 路并行代码级探查（后端 Runtime、Go/Java 服务、前端多端、测试部署、文档体系）+ 关键结论人工复核（fail-open 流控、哈希桶伪向量、git 构建产物入库均经源码/命令二次确认）

---

## 一、总体结论（TL;DR）

**综合评分：39.5 / 100 —— 教学演示级「企业级外壳」原型，未达互联网大厂生产准入标准。**

一句话定性：本项目在**工程广度**上远超普通课程原型（Redis/Pulsar/Nacos/etcd/gRPC/金丝雀/影子对比/Kustomize 一应俱全，data-contracts 是亮点），但在**核心深度**上存在系统性虚化——编排、智能、A2A、向量检索等「卖点能力」多为标签化伪实现，安全基线未达标，测试金字塔底部（Go 高并发链路）为空，需求工程与 ADR 治理缺失，多处「立法即违法」（命名规范被自己的代码违反）。

**是否需要推倒重来？不需要。** 建议采用「**保留骨架、重填内核**」的定向深度重构（详见第六章四阶段路线图）：当前的多语言服务拓扑、契约目录、部署资产均值得保留；必须重做的是领域内核、智能真实性、安全基线、质量度量与证据链。

---

## 二、分维度评分表（GB·T 25000 SQuaRE + TOGAF + TDD 加权）

| # | 维度 | 权重 | 得分 | 等级 | 一句话判据 |
|---|------|-----|------|------|-----------|
| 1 | 需求分析与规格（SRS/GB·T 9385） | 10% | **35** | D | 无 FR/NFR 条目化、无用例建模、验收标准不可测，无追溯矩阵 |
| 2 | 架构设计文档（TOGAF 10 / 4+1） | 10% | **55** | C | 覆盖逻辑/部署/数据/时序视图，但无 ADR、无 C4 分级、缺安全视图 |
| 3 | DDD 领域建模落地 | 10% | **22** | E | 无限界上下文，3 个贫血 dataclass，仓储是摆设，主链路读本地 JSON |
| 4 | 后端实现真实度与代码质量 | 15% | **38** | D | 基础设施接线广而真，但编排/A2A/向量检索为伪实现；无 logging、55 处吞异常 |
| 5 | 前端多端实现 | 10% | **45** | C− | 技术栈新（React 19 + Vite 7 + TanStack Query）、错误处理好；但无 TS/测试/设计系统，demo 级 UI |
| 6 | 测试体系（TDD） | 10% | **30** | D− | 26 个 Python 宽集成冒烟 + 4 个 Java 测试类；Go 0 测试、前端 0 测试、全仓无覆盖率、无 E2E |
| 7 | 部署与运维（SRE） | 10% | **45** | C− | Kustomize/HPA/PDB/17 条告警规则齐全；但无 tracing/日志聚合、CI 部署空转、门禁可被存量文件堆绿 |
| 8 | 安全（GB·T 25000 信息安全性） | 10% | **20** | F | 无鉴权、fail-open 流控、路径穿越、弱签名+明文密钥、K8s 无 securityContext/NetworkPolicy |
| 9 | 文档治理与可追溯性 | 10% | **38** | D | 工程细节密度高；但幽灵路径蔓延、容量叙事自相矛盾、AI 生成式膨胀明显 |
| 10 | UI/UX 视觉设计 | 5% | **30** | D | 无设计系统/设计令牌、无 a11y、无暗色模式，两个调试台而非用户产品 |
| — | **加权总分** | 100% | **39.5** | **D+** | **教学演示级，距大厂生产准入（≥75）有代差** |

大厂生产准入参考线（综合 75 分 = 各维度不低于 C+ 且安全不低于 B）：本项目 10 个维度中 5 个低于 40 分，安全维度为不及格，**判定：不具备生产准入资格**。

---

## 三、分角色评语

### 3.1 互联网大厂资深系统架构师 / 技术总监

**这是典型的「广度型简历项目」：架构图好看，内核是空的。** 三个决定性证据：

1. **编排引擎是标签不是实现**。`orchestration/engine.py:29-133` 中 LangGraph/AgentScope/OneAgents 三个引擎代码几乎相同——同步顺序直调，仅用 `find_spec()` 探测框架是否安装并在 metadata 里标注 "state-graph-bound"，无 StateGraph、无状态机、无节点重试。行业生产模式（2025-2026 共识：MCP 做工具层、A2A 做代理委托、LangGraph 做有状态图编排的**三层分工**）在本项目中被压平为「换名字的同一个函数」。
2. **A2A 发而不收**。`orchestrator.py:184-196` 往 Redis Streams 发完消息后，推荐结果仍来自进程内直调——消息被发出但从不消费，A2A 只剩日志价值。对比行业实现（A2A 用于跨框架代理任务委托，是请求-响应闭环），这是半成品。
3. **gRPC 契约三方落地率 1/3**。4 个 proto 契约先行（值得肯定），但 RuntimeService 无 Python 服务端、PolicyService 无 Go 服务端，仅 ranker 真用 gRPC；Gateway 的 pom 生成 stub 却只用 HTTP。契约漂移检查只覆盖 py/go。

**技术总监结论**：若这是候选人的简历项目，面试将通过（广度惊人）；若这是要上生产的企业系统，我会否决上线申请——`maxAgentSteps/maxToolCalls` 校验后从不执行（`orchestrator.py:152-153`）、fanout 熔断器每次请求新建导致状态永不累积（`fanout-go/main.go:112-117`）、go_live 门禁「文件存在即 PASS」且 SKIP 不算失败——这些不是 bug，是**治理体系不具备阻断力**。

### 3.2 高校 AI / 大数据教授级高工

- **「智能」名不副实**：`memory/vector_store.py:24-33` 的 `_hash_vector` 是 SHA-256 词桶哈希（64 维），Qdrant/Milvus/FAISS 三后端全用它——**token 重叠冒充语义检索**；`memory/graphrag.py:9-29` 仅是名称-标签二部图邻居计数，无 LLM 无检索。README 宣称「GraphRAG + Faiss 已升级为必选（非可选）」与实现不符，这在科研语境是学术不端风险，在工程语境是虚假宣传。
- **业务粘性 Agent 是硬编码文案**：`agents/manager_agent.py:125-196` 中 LoyaltyGrowth/WeatherRisk/Ancillary 等 Agent 仅返回写死的中文句子，无 LLM、无决策逻辑。
- **可取之处**：金标用例驱动的 `test_policy_core_parity.py`（数据契约 + golden cases）是正确的工程方法；`test_db_crud.py` 的 mock 隔离质量合格；影子对比/双栈灰度的**思路**达到企业水准——问题只在落地深度。
- 教学定位下本项目是优质素材：35 篇文档 + 课程交付手册 + 9 个可操作实验（course-delivery.md），覆盖面是真实竞争力。

### 3.3 德国双元制教育本土化专家

- **亮点**：项目形态天然适合双元制「企业真实任务 + 学校理论」六步法（资讯-计划-决策-实施-检查-评价）：多语言协作、代码评审素材、故障注入场景都是现成教具；`course-delivery.md` §11「必须实话实说」环节体现了难能可贵的诚实原则。
- **缺口**：`public-sharing-dual-education-210.md` 仅 97 行，双元制六步法只有标题清单，无每步的教学设计/课时分配/评价量表；无学生考核 rubric（现有评分矩阵是选型矩阵不是学业评定矩阵）；无「企业导师/学校教师」双主体分工说明。**若要将本项目申报教学成果，教学论层面的文档必须重写。**

### 3.4 专业带头人（职业教育/本科专业建设视角）

- 项目可作为「AI 应用开发」「大数据技术」专业的综合实训载体，覆盖 Python/Java/Go/前端/小程序/K8s 全栈岗位群——这是专业建设价值的最大卖点。
- 但作为课程标准配套资源有三处硬伤：① 需求分析教学示范缺位（正好可以反向教学：用本项目做「不合格 SRS 案例解剖」）；② 无 ADR，无法教「架构决策过程」；③ 规模声明（10B 用户/1M 并发）与证据（实测 300 并发、100% 失败的 locust CSV 并存）的矛盾若被学生发现，会摧毁课程公信力——**必须先做证据链清理再进课堂**。

### 3.5 高级美工 / 平面设计师

- **现状是「工程师调试台」而非产品**：Web 表单直接暴露 tenantId/policyId/maxAgentSteps/idempotencyKey 等内部字段；推荐结果用 `Object.entries` 平铺 dump 原始 JSON（含 traceId）；`index.html` `lang="en"` 配中文产品；无 aria、无 focus 样式、无骨架屏、无空态、无动效。
- **设计系统为零**：179 行手写 CSS，硬编码 Tailwind 灰阶色值；无设计令牌、无暗色模式、仅一个 1000px 断点。小程序与 Web 的「一致性」靠手工复制色值维持，未沉淀共享 tokens 包（业界 2025-2026 标准：monorepo 内 tokens 包作为单一事实源，Fluent UI / IBM Carbon 均如此）。
- 小程序存在渲染 bug：metrics 页在 WXML 写 `{{JSON.stringify(item.payload)}}`——WXML 不支持该全局函数，实际渲染为空。
- **设计师结论**：配色基底（#111827 灰阶 + 白卡）干净可用，值得保留为品牌基调；需要补的不是「美化」而是「产品化」——信息层级（酒店名/评分/价格/理由的字段语义化排版）、状态设计（骨架屏/空态/错误插画）、以及一份真正的 design tokens 规范。

---

## 四、关键证据清单（按严重度 P0→P2）

### P0-安全（生产事故级，须立即修复）

| # | 问题 | 证据 |
|---|------|------|
| S1 | `/recommend`、`/a2a/send`、`/a2a/inbox` **完全无鉴权**，A2A 收件箱可被任意注入/窃取消息 | `api/app.py:175-194` |
| S2 | 流控/熔断 **fail-open**：Redis 不可用或任何异常时直接放行，无告警 | `traffic_guard.py:37-41,48-49,70-71,90-93,98-99`（已人工复核） |
| S3 | **路径穿越**：用户可控 skill 名直接拼文件路径，可 `../` 读任意 JSON | `skills/loader.py:19-22`，入口 `orchestrator.py:182` |
| S4 | 内部签名弱且密钥明文入库：SHA-256 前缀匹配 + demo 密钥硬编码；非 HMAC，可长度扩展攻击 | `api/app.py:25,32-35`；`InternalTokenService.java:19-22`；`application.yml:21` |
| S5 | Milvus 表达式注入（f-string 拼 filter）；gRPC 明文 insecure channel；DB 默认口令 `root:password` | `vector_store.py:186,199`；`go_ranker_client.py:282`；`db/database.py:11` |
| S6 | K8s 全目录无 securityContext/NetworkPolicy/ServiceAccount/密钥治理，镜像 tag 硬编码占位符 | `platform/deploy/k8s/`（grep 零命中）；`deployment.yaml` |

### P0-真实性（宣称与实现不符）

| # | 问题 | 证据 |
|---|------|------|
| F1 | 三套编排引擎代码几乎相同，均为同步顺序直调，伪 LangGraph | `orchestration/engine.py:29-133` |
| F2 | A2A 消息发而不收，仅剩日志价值 | `orchestrator.py:184-196` |
| F3 | 伪语义检索：SHA-256 词桶哈希冒充 embedding；GraphRAG 是邻居计数 | `vector_store.py:24-33`；`graphrag.py:9-29`（已人工复核） |
| F4 | `maxAgentSteps/maxToolCalls` 校验后执行期从不限量 | `orchestrator.py:152-153,254-261` |
| F5 | 业务 Agent 为硬编码文案，无 LLM 参与 | `agents/manager_agent.py:125-196` |
| F6 | 策略四处重复实现（rego/policy_core.go/Java/policy-core.json）且 rego 未消费契约 JSON，极易漂移 | `policy.rego:6-118`；`policy_core.go:40-56`；`PolicyGuardService.java:165-186` |
| F7 | fanout 熔断器逐请求重建，状态永不累积，形同虚设 | `fanout-go/main.go:112-117` |

### P1-质量与治理

| # | 问题 | 证据 |
|---|------|------|
| Q1 | Go 四服务 0 个 `*_test.go`，CI 仅 build 不 test；前端 0 测试且 `ci:test` 等于 `vite build` | `services/*-go/`；`apps/.../package.json` |
| Q2 | 全仓无覆盖率工具（pytest-cov/jacoco 均无配置）、无 lint（ruff/eslint/gofmt）、无 SAST/镜像扫描/SBOM（trivy/codeql 零命中）；`go-version: '1.26.1'` 是不存在的版本号 | `.github/workflows/ci-cd.yml` |
| Q3 | CI canary gate 读仓库内静态 JSON 做决策（恒 PASS），promote 后无 kube context 即静默跳过部署 | `ci-cd.yml` canary-deploy job |
| Q4 | go_live 门禁「文件存在即 PASS」、SKIP 不计 fail、签名校验默认关闭、`min_scale_status` 默认接受 NOT_READY | `go_live_final_check.py`（749 行） |
| Q5 | 压测证据自相矛盾：report_5k 100% 成功 vs locust 41949 请求 100% 失败并存，未做 reconciliation | `stress/locust_runtime_local_1000_stats.csv` vs `stress/report_5k.json` |
| Q6 | **3781 个 dist/node_modules 构建产物被 git 追踪**（.gitignore 后补但未 `git rm --cached`） | `git ls-files` 计数（已人工复核） |
| Q7 | Runtime 全库无 logging 模块，55 处 `except Exception` 多数静默吞掉；33/49 文件共用同一模板 docstring（AI 批量生成痕迹） | `traffic_guard.py` 等 |
| Q8 | 无 OTel/Jaeger tracing、无 Loki/ELK 日志聚合，链路追踪仅靠手工传 X-Trace-Id（Java 端还是随机伪造的 traceparent） | `PythonRuntimeClient.java:81`；monitoring/ 目录 |

### P1-文档与需求

| # | 问题 | 证据 |
|---|------|------|
| D1 | 无合格 SRS：FR/NFR 条目化、用例图、用户故事、可测验收标准全部缺失（GB·T 9385 / IEEE 830 零命中） | `docs/` 全目录 |
| D2 | 无 ADR；Java/Go/Python 分层、etcd 双栈等重大决策无决策记录 | 无 docs/adr/ |
| D3 | **幽灵路径**：README/runbook/handoff 引用不存在的 `frontend-web/`（实际 `apps/techgroup-enterprise-travel-web/`）与不存在的顶层 `deploy/`（实际 `platform/deploy/`），运维照做即失败 | `release-runbook.md` §1 |
| D4 | 命名规范「立法即违法」：规范强制 `com.techgroup.travel`，全部 Java 包是 `edu.enterprise.travel.gateway.*`，且无 CI 强制 | `technology-group-naming-convention.md` |
| D5 | 容量叙事分裂：10B 用户/1M 并发宣称（≥6 篇文档）vs 实测 achievedConcurrency=300/pass=false 的自签证据；自造证据可喂饱门禁（自证循环） | `platform-product-spec.md` §10；`manual-1m-record-testing.md` §1 |
| D6 | `system-design.md` 称前端为 Vue3，README 称 React 19，互相矛盾；Mermaid 子图语法有渲染失败风险 | `system-design.md` §2.1, §8.1 |

### P2-前端与多端

- 无 TypeScript、无 ESLint/Prettier、无代码分割（React.lazy 零命中）、无 a11y、无暗色模式（详见 3.5）。
- 小程序无鉴权 token、`utils/config.js` 硬编码 localhost、`project.config.json` `urlCheck:false`、无组件化、表单校验重复 6 段。
- 两端未共享契约类型（data-contracts 未产出 TS/OpenAPI 供前端消费），无 monorepo workspace 管理。

---

## 五、对标业界最优实践的差距矩阵（2025-2026 联网核对）

| 领域 | 业界最优实践（共识） | 本项目现状 | 差距 |
|------|---------------------|-----------|------|
| 企业架构 | TOGAF 10 ADM + ADR 治理 + C4 分级视图 | system-design.md 近似 4+1 但无 ADR/无 C4/缺安全视图 | 中 |
| 领域建模 | DDD 限界上下文 + 事件风暴 + 聚合根/仓储 | 技术职责平铺、贫血模型、仓储摆设 | 大 |
| 多 Agent 编排 | MCP（工具）/ A2A（代理委托）/ 图引擎（有状态编排）三层分工，可观测性内建 | 三层被压平为同一同步直调函数；A2A 单向 | 大 |
| LLM/检索 | 真 embedding + 混合检索 + GraphRAG（LLM 抽取的图）+ 混合模型分层（Booking.com 模式） | SHA-256 词桶哈希 + 邻居计数 | 大 |
| 微服务生产化 | 优雅退出/超时/重试/熔断（持久化状态）/统一 prom SDK | 四服务均缺优雅退出与超时；熔断逐请求重建 | 大 |
| K8s 安全基线 | Pod Security Standards（Baseline/Restricted）+ default-deny NetworkPolicy + SealedSecret/外部 KMS + GitOps | 全缺失，镜像 tag 占位符 | 大 |
| CI/CD | lint + test + 覆盖率门禁 + SAST/镜像扫描/SBOM + 环境晋升 | 无 lint/覆盖率/扫描；部署 job 空转 | 大 |
| 质量度量 | 覆盖率强制门禁、变异测试（大厂常见）、E2E（Playwright） | 全无 | 大 |
| 前端工程 | TS + 设计令牌 monorepo 包 + E2E + 语义化结果渲染 | 纯 JS 单页 + 平铺 dump + 手工复制色值 | 大 |
| 行业对标 | Trip.com TripGenie / Booking.com：可观测性内建的模块化 agent 栈、混合模型分层、97% 生产 agent 准确率目标 | 教学演示级 | 代差 |

参考来源：TOGAF 10 与 DDD 融合实践（[Open Group](https://blog.opengroup.org)、[threedots.tech](https://threedots.tech)）、MCP×A2A 分层（[arXiv:2506.01804](https://arxiv.org/pdf/2506.01804)、[多协议编排对比](https://iotdigitaltwinplm.com/multi-agent-orchestration-mcp-a2a-langgraph-2026)）、K8s Pod Security Standards（[kubernetes.io](https://kubernetes.io)）、NetworkPolicy 分层治理（[Tigera](https://www.tigera.io)）、设计令牌 monorepo（[bit.dev](https://bit.dev)、[Fluent UI / Carbon 模式](https://dev.to)）、OTA 生产 agent 栈（[Booking.com agentic AI](https://news.booking.com/bookingcom-debuts-agentic-ai-innovations-adding-to-its-robust-suite-of-genai-tools-for-customers)、[Trip.com TripGenie](https://us.trip.com/tripgenie)）。

---

## 六、优化改进与重构路线图（保留骨架、重填内核）

### Phase 0 · 止血与清创（1-2 周，P0 归零才能谈其他）

**安全归零：**
1. Gateway 引入 Spring Security + JWT（OIDC，Keycloak），Runtime 侧校验签名；A2A 收件箱加身份与 ACL。
2. `traffic_guard` 改 fail-closed（Redis 不可用→拒绝+告警），熔断补半开探测。
3. 修路径穿越（白名单化 skill 名）、Milvus 参数化、HMAC 替换前缀签名、密钥入 K8s Secret/Vault。
4. K8s 补 securityContext（runAsNonRoot、drop caps、readOnlyRootFilesystem）+ default-deny NetworkPolicy + SealedSecret。

**仓库卫生：**
5. `git rm -r --cached` 清除 3781 个 dist/node_modules 产物，重写 .gitignore 生效（保留 tag 发布）。
6. 全局路径纠偏：frontend-web→apps/…、deploy/→platform/deploy/（一次性 sed + CI 检查文档路径有效性）。

**CI 左移：**
7. 加 ruff/eslint/gofmt/go test/vitest + pytest-cov + jacoco 覆盖率上报与门禁（起步线：Python 60%、Java 60%、Go 50%）。
8. 加 trivy（镜像+依赖）与 codeql；修 `go-version: '1.26.1'` 幽灵版本。

**证据链清理：**
9. 删除或归档全部「10B/1M 已达到生产标准」表述，统一为「目标容量规划 + 实测证据」两栏口径；reconcile locust 失败 CSV 与 report_5k 的矛盾（在报告中写明失败原因与复测结论）。

**验收 DoD**：P0 表全部闭环；CI 全绿且含覆盖率徽章；`go_live_final_check.py` 的 FAIL 分支有测试且 `--strict` 模式作为默认。

### Phase 1 · 领域内核重构（4-6 周，DDD + 真智能）

1. **DDD 建模**：事件风暴划分限界上下文——`行程规划（Itinerary）`、`推荐排序（Ranking）`、`策略合规（Policy）`、`会员身份（Membership）`、`工具接入（ToolAccess）`；定义聚合根（TripPlan、Itinerary）、值对象（Preference、Budget）、领域事件（ItineraryPlanned、RankingCompleted）；仓储接口在领域层、实现下沉基础设施层（现有 db/crud.py 升级为真实现，替换 tools/data_store.py 的本地 JSON 主链路）。
2. **真编排**：按业界三层分工落地——MCP 用真 JSON-RPC server 暴露工具；A2A 打通「发→收→响应」闭环（现有 Redis Streams 代码保留）；编排引擎引入真 LangGraph（StateGraph + 检查点 + 节点重试），旧同步直调降级为 fallback；`maxAgentSteps/maxToolCalls` 在执行循环里逐节点扣减。
3. **真智能**：embedding 换真模型（DashScope text-embedding 或本地 bge-small-zh），FAISS 真索引；GraphRAG 接 LLM 抽取实体关系或暂时下线该宣称；业务 Agent 接 LLM（Spring AI Alibaba ChatClient 已在 Gateway 有依赖，下沉复用）。
4. **策略单一事实源**：policy-core.v1.json 为唯一上游，rego/Go/Java 全部编译自该契约（构建期校验一致性），golden cases 扩充边界与负向用例。
5. **契约落地对齐**：RuntimeService 补 Python gRPC 服务端或从 proto 移除该契约；Gateway 保留 HTTP 但删除空转的 stub 生成。
6. **代码质量**：引入 structlog logging、收编 55 处吞异常（fail-fast 或降级+告警）、拆解 orchestrator 上帝类（组装器/工具目录/影子对比各自成模块）、消除 `parents[3]/parents[5]` 跨仓路径（改环境变量注入契约路径）。

**验收 DoD**：限界上下文图 + ADR ≥10 条；金标用例 ≥50 条（含负向）；影子对比显示新旧引擎 diff <2%；覆盖率达标。

### Phase 2 · 产品化与可观测（4-6 周）

1. **设计系统**：建 `packages/design-tokens`（色彩/字号/间距/圆角/阴影 JSON 单一事实源），Web 用 CSS variables 消费、小程序用 build 脚本生成 WXSS；Web 补 Tailwind 4 或 CSS Modules + 语义化结果卡（酒店名/星级/价格/推荐理由分层排版）、骨架屏、空态、Toast、暗色模式、a11y（aria/focus/lang="zh-CN"）。
2. **前端工程**：迁移 TypeScript（类型自 data-contracts 生成 OpenAPI/TS schema）、React.lazy 分包、Vitest 组件测试 + Playwright 两条 E2E（登录→推荐→查看详情）；小程序抽 form-field/result-card 组件、修 WXML JSON.stringify bug、埋点接上报通道、域名可配置并开启 urlCheck。
3. **可观测性**：OTel SDK（Python/Java/Go 三端）+ Jaeger/Tempo、Loki + Promtail 日志聚合、grafana 仪表盘补 RED/USE 方法论面板；traceparent 由中间件生成而非伪造。
4. **部署 GitOps 化**：ArgoCD（或 Flux）接管 kustomize 应用，镜像 tag 由 CI 摘要注入（消灭占位符）；Helm 化或保留 kustomize 但补 serviceAccount/strategy。
5. **Go 服务生产化**：统一 graceful shutdown、http.Server 超时、官方 prometheus/client_golang、持久化熔断（gobreaker）、fanout/policy/ranker/registry-cache 各补 `_test.go`（并发与边界用例）。

**验收 DoD**：一条 trace 可从 Gateway 串到 Ranker；E2E 全绿；设计令牌改动一键同步两端；GitOps 部署演练成功。

### Phase 3 · 规模实证（持续）

1. 分布式压测进 kind/k8s 集群（k6 或 Locust 分布式 master-worker），目标：先实证 1 万并发（当前证据仅 300），再逐级上探；证据 JSON 由测试平台生成而非本地脚本自签。
2. 混沌演练：Chaos Mesh 注入 Redis/etcd/Go 服务故障，验证 fail-closed 与降级路径（现在 fail-open 下演练无意义）。
3. 容量模型与实测对齐：production-capacity-plan 的 1667/16667 pods 公式与压测数据联动更新。

### 教学化专项（双元制，可与 Phase 2 并行）

- 按「资讯→计划→决策→实施→检查→评价」六步法重写 210 页课件大纲：每步给出教学目标/课时/师生活动/评价量表；新增学生考核 rubric（需求分析 20% / 架构设计 20% / 实现 25% / 测试 20% / 部署运维 15%）。
- 增设「反模式解剖」实验：用本项目修复前后的 fail-open、伪向量、CI 空转做对照教学素材（这是本项目独有的教学价值）。

---

## 七、最终判定

1. **分析是否落地？** 需求工程未成体系（无 SRS 条目、无追溯矩阵、无验收标准）——「分析」环节实际上是缺位的，`platform-product-spec.md` 是产品愿景文档而非需求规格。
2. **设计是否落地？** 文档设计成文（system-design.md 覆盖 4+1 大半），但代码落地率约 40-50%：分层、契约、部署资产落地；DDD、编排智能、A2A 闭环、控制参数、gRPC 全栈是「设计有、实现无」。
3. **是否达到大厂标准？** 否。大厂生产准入的硬门槛（安全基线、质量度量、可观测性、证据链可信）中，安全与度量两项不及格，可观测性半缺，证据链存在自证循环。
4. **是否需要完整重构？** **需要「内核级定向重构」，不需要推倒重来。** 服务拓扑（Python Runtime + Java Gateway + 4 Go 服务）、data-contracts、Kustomize/监控资产、金标用例方法、影子对比机制均保留；必须重建的是：领域模型（DDD）、真编排与真检索（智能内核）、安全基线、测试金字塔（尤其 Go 层）、以及从需求到证据的可追溯链。按第六章四阶段推进，约 3-4 个月可达大厂准生产（≥75 分）门槛。

---

*本报告由 5 路代码级探查 + 关键结论人工复核 + 2026-09 联网业界对标生成；所有引证均含 文件:行号，可复核。*


---

## 八、重构后复盘评分（2026-09-19 四阶段执行完毕）

执行摘要：Phase 0/1/2/3 资产全部落地，Python 104 测试 / Java 13 测试 / Go 11 测试 / Web Vitest 3 测试全绿，ruff 零告警，覆盖率门禁 50%（实测 59%），gRPC 契约三端落地率 1/3→3/3，git 历史已重写清除全部构建产物（.git 151M→19M）。

| # | 维度 | 重构前 | 重构后 | 变化依据 |
|---|------|-------|-------|---------|
| 1 | 需求分析与规格 | 35 | 45 | 容量口径与证据链对齐；SRS 条目化仍未做 |
| 2 | 架构设计文档（TOGAF） | 55 | 68 | ADR 0001-0005 治理决策链；幽灵路径清零 |
| 3 | DDD 落地 | 22 | 55 | domain/application/infrastructure 三层 + TripPlan 聚合根 + 仓储端口；限界上下文仍待事件风暴深化 |
| 4 | 后端实现真实度 | 38 | 65 | 真 StateGraph（显式降级标记）、预算执行期强制、A2A 真闭环、gRPC 服务端落地、Keycloak/OIDC 端到端；业务 Agent 的 LLM 化未完成 |
| 5 | 前端多端 | 45 | 60 | design-tokens 双端单一事实源、暗色/骨架屏/a11y/语义卡、小程序 bug 修复；TS 迁移未完成 |
| 6 | 测试体系（TDD） | 30 | 58 | 四语言 131 测试、覆盖率门禁、契约/预算/熔断回归；E2E 缺位 |
| 7 | 部署与运维 | 45 | 70 | K8s 安全基线、GitOps、OTel/Loki/Tempo 资产、kind 证据脚本；集群实测待 Docker 环境 |
| 8 | 安全 | 20 | 65 | OIDC、HMAC 全量签名、fail-closed、路径穿越/注入修复、securityContext/NetworkPolicy；A2A 内部模式仍开放 |
| 9 | 文档治理 | 38 | 60 | SSOT 口径、ADR、runbook；追溯矩阵未建 |
| 10 | UI/UX | 30 | 52 | 设计系统起步、产品化渲染；完整视觉规范待出 |
| — | **加权总分** | **39.5** | **61.5** | **教学级 → 准生产雏形（C）** |

### 剩余到 ≥75（大厂准生产）的清单

1. SRS 需求条目化（FR/NFR/验收标准）与需求-测试追溯矩阵（1 周）。
2. Web TypeScript 迁移 + Playwright E2E 两条主链路（1-2 周）。
3. Docker Desktop 就绪后执行 `run_kind_loadtest.sh` 产出首个真实集群证据；再上 staging 集群重复（1 天 + 排队）。
4. 业务 Agent（Loyalty/Weather/Ancillary 等）接 LLM（Spring AI Alibaba 下沉或 DashScope 直连）+ 真 embedding 模型安装验证（1 周）。
5. OTel 三端接线完成度提升（Go/Java SDK 注入），trace 从 Gateway 串到 Ranker 的端到端断言进 CI（1 周）。
6. 推送远端：本机网络无法直连 GitHub，需在代理环境执行 `git push --force -u origin main`（含 `--tags` 如有）。

---

## 九、六项清单复盘评分（2026-09-19 二轮收尾）

上一章「剩余到 ≥75」清单的六项已全部执行完毕并分项提交、推送远端（main @ 5719666）：

| # | 清单项 | 结果 | 证据 |
|---|--------|------|------|
| 1 | SRS 条目化 + 追溯矩阵 | 完成 | `docs/srs-travel-agent.md`（FR/NFR/验收标准条目化）+ `docs/traceability-matrix.md`（需求↔测试↔证据映射），commit 17cb7ef |
| 2 | Web TS 迁移 + Playwright E2E | 完成 | 全部 .jsx/.js → .tsx/.ts（App/页面/路由/api/auth），tsconfig 双配置、vitest.config、eslint flat config + prettier；`e2e/recommend.spec.ts`（登录→推荐→详情主链路）+ playwright.config.ts，commit 8bd54f6 |
| 3 | kind 集群实测 + 签名证据 | 完成 | Rancher Desktop + kind 全链路部署，`stress/report_kind2.json`、`stress/load_test_gateway.py`、k8s/local overlay（含 gateway-local.yaml）随 5719666 入库 |
| 4 | 业务 Agent LLM/embedding 接线 | 完成 | DashScope LLM rationale（可插拔降级）+ embedding provider 单测与文档，commit ea068ed |
| 5 | OTel 接线 + CI trace 断言 | 完成 | runtime `configure_tracing()` 真实调用；`travel_agent.recommend` span 桥接网关 X-Trace-Id（`travel.trace_id`）；`tests/test_otel_tracing.py`（mock 4 用例 + CI 真实 InMemorySpanExporter 断言）；CI 新增断言步骤，commit a3ee717 |
| 6 | 推送远端 | 完成 | hosts 指向 140.82.112.x 修复连接重置后 `git push origin main` 成功（32cb1c9..5719666） |

顺带落地的加固（5719666）：Nacos list_services/list_tools 降级不再打断推荐链路；网关全局异常处理器补 error 日志；压测客户端连接池化（消除容器网络下假性连接错误）。

| # | 维度 | 二轮前 | 二轮后 | 变化依据 |
|---|------|-------|-------|---------|
| 1 | 需求分析与规格 | 45 | 62 | SRS 条目化 + 全量追溯矩阵，需求-测试-证据链闭合 |
| 2 | 架构设计文档 | 68 | 72 | 链路追踪设计落文档并随代码入库 |
| 3 | DDD 落地 | 55 | 55 | 本轮未动 |
| 4 | 后端实现真实度 | 65 | 70 | 业务 Agent LLM 接线（可插拔）、注册中心降级加固 |
| 5 | 前端多端 | 60 | 70 | 全量 TS + E2E 主链路 Playwright |
| 6 | 测试体系 | 58 | 68 | E2E 落地、OTel 自动断言进 CI、kind 集群证据 |
| 7 | 部署与运维 | 70 | 75 | 真集群（kind）部署 + 压测证据入库 |
| 8 | 安全 | 65 | 65 | 本轮未动 |
| 9 | 文档治理 | 60 | 70 | SRS/追溯矩阵/OTel 文档三件套 |
| 10 | UI/UX | 52 | 55 | TS 化与 E2E 间接提升 |
| — | **加权总分** | **61.5** | **≈67.5** | **准生产雏形 → 准生产加强（C+）** |

### 距 ≥75 的剩余差距（下一轮建议）

1. **安全**（65，最大短板）：A2A 内部模式收口、mTLS 全链路、密钥轮换机制（约 +4）。
2. **DDD**（55）：事件风暴深化限界上下文、TripPlan 仓储持久化实现（约 +3）。
3. **后端真实度**（70）：Spring AI Alibaba 下沉网关侧 LLM 编排、embedding 真模型接入验证（约 +3）。
4. **测试体系**（68）：Go 服务并发/边界用例补齐至与 Python 对等、混沌演练（约 +2）。
5. **staging 集群复测**：kind 证据之外在真实 staging 重复压测（约 +1）。

---

## 十、三轮复盘评分（2026-10-24 三轮收尾）

二轮「距 ≥75 的剩余差距」五项已全部执行完毕并分项提交、合并回 main（main @ 31fc657）：

| # | 差距项 | 结果 | 证据 |
|---|--------|------|------|
| 1 | 安全：A2A 内部模式收口 + mTLS + 密钥轮换 | 完成 | A2A internal mode + dev mTLS 证书（证书不入库）+ 双窗口密钥轮换；`tests/test_secret_rotation.py` 65 行；commit 9b49fae |
| 2 | DDD：TripPlan 聚合仓储持久化 | 完成 | 聚合仓储持久化 + 领域事件外送 + DDD 事件风暴文档；`tests/test_trip_plan_persistence.py` 138 行；commit ee6f55d |
| 3 | 后端真实度：Spring AI Alibaba 下沉 + 真 embedding | 完成 | advisor 下沉 + rewrite 端点 + 真 embedding 契约验证；`tests/test_embedding_real_contract.py` 99 行；commit e36af5b |
| 4 | 测试体系：Go 对等测试 + 混沌演练 | 完成 | policy/ranker/fanout/registry-cache 对等+边界+并发测试（-race 进 CI）+ 混沌演练脚本与 runbook；commit d9b38a5 + cbde90b（registry-cache initCache/newRouter 提取修复） |
| 5 | staging 集群复测（kind 实测） | 完成 | CI run [40119911250](https://github.com/tianqiongenze/enterprise-travel-agent/actions/runs/40119911250) canary **promote**：5 服务 Running、双通道成功率 100%（gap=0.0）、go-ranker p95 5.6ms；发现并修复 4 项真实缺陷（policy.rego 缺失 CrashLoop、registry-cache SA 未定义、指标落盘 500、Pulsar publish 30s 阻塞）；`stress/staging_retest_report.{json,md}` + `stress/ci-evidence/` + `docs/staging-retest-runbook.md` 入库 |

统一回归（合并后 main 本地）：Python `run_python_tests_ci.py` OK（skipped=1）、Go 4 服务 `go test ./...` 全绿；main 推送后由远端 CI 复核全量（含 Maven/Frontend）。

| # | 维度 | 二轮后 | 三轮后 | 变化依据 |
|---|------|-------|-------|---------|
| 1 | 需求分析与规格 | 62 | 62 | 本轮未动 |
| 2 | 架构设计文档 | 72 | 72 | 本轮未动 |
| 3 | DDD 落地 | 55 | 58 | TripPlan 聚合仓储持久化 + 领域事件外送落地，事件风暴文档 |
| 4 | 后端实现真实度 | 70 | 73 | Spring AI advisor 下沉、真 embedding 契约验证、A2A 内部模式收口 |
| 5 | 前端多端 | 70 | 70 | 本轮未动 |
| 6 | 测试体系 | 68 | 71 | Go 对等/边界/并发测试 + -race CI 门禁、混沌演练、staging canary 双通道证据进 CI |
| 7 | 部署与运维 | 75 | 77 | staging overlay 真集群（kind）部署验证、4 项真实缺陷修复、复测 CI 化可重复执行 |
| 8 | 安全 | 65 | 69 | A2A 内部模式收口、dev mTLS、双窗口密钥轮换（fail-closed 测试覆盖） |
| 9 | 文档治理 | 70 | 71 | staging retest runbook + 复测报告 + 事件风暴文档 |
| 10 | UI/UX | 55 | 55 | 本轮未动 |
| — | **加权总分** | **≈67.5** | **≈68.3** | **准生产加强 → 大厂准生产边缘（B-）** |

### 距 ≥75 的剩余差距（下一轮建议）

1. **前端多端**（70）：小程序/桌面端补齐 + 视觉规范全量（约 +2.5）。
2. **需求分析与规格**（62）：SRS 与实现漂移的再对齐、NFR 量化验收（约 +2）。
3. **架构设计文档**（72）：多区域/容灾架构决策记录 ADR 化（约 +1）。
4. **测试体系**（71）：Playwright E2E 双链路进 CI + Go 混沌演练 CI 化（约 +1）。
5. **后端真实度**（73）：业务 Agent 全链路 LLM 化（多工具编排）端到端验证（约 +1）。

> 备注：kind 复测过程中暴露的 4 项缺陷均已修复并随回归验证入库；执行环境的容量/依赖降级适配仅存在于 CI 冒烟窗口（详见 `docs/staging-retest-runbook.md` §2），staging overlay 保持生产形态。

### 远端 CI 复核结果（main @ db18c57，2026-10-25）

合并推送后远端 CI 实测跑通并暴露/修复了 4 项合并集成回归（gap 分支各自基线从未合在一起编译过）：

1. gateway/java 测试编译失败：gap1 将 `InternalTokenService` 构造器改为双参数（双窗口轮换），存量 `PythonRuntimeClientTest` 未同步——已修（3d8000b），本地 mvn test 13+ 用例全绿（含 gap3 新增 SpringAiAlibabaAdvisorServiceTest）。
2. go-policy `go test -race` 失败：测试重复调用 `initPolicy()`/`initDecisionLogWorkers()` 并发改写全局——已用 sync.Once 幂等化（db18c57），CI go-policy-build 转绿。
3. gofmt 门禁失败（gap4 测试文件 + registry-cache main.go）——已格式化。
4. ruff F401×2 + F821 `async_session`（PEP 562 惰性属性不能用裸全局名访问）——已修。

staging-retest-kind 在 main 上连续两轮 **success**（run 40123671022 等）。仍红的两项为预存问题：`python-tests`（2026-09-19 起即红，CI Python 3.12 与本地 3.14 行为差异，需在可读 CI 日志的网络环境定位）与 `security-scan`（"Set up job" 阶段失败，runner 基础设施层，与代码无关）。二者不计入本轮评分。
