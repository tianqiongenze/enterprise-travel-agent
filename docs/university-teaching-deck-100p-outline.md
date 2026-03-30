# 《企业级智能旅游多 Agent 推荐系统》百页级高校教学 PPT 大纲

> **使用说明**：本文件为专门为大学课堂设计的高校全栈架构教学 PPT 核心内容逐页分镜大纲。包含了大语言模型、微服务架构(Java/Go/Python)、高并发海量数据处理(Redis/ShardingSphere)等基础背景知识与项目实战代码应用。适合作为《大型分布式软件架构实战》或《AI 智能系统与后端工程》的学期主干教材。

---

## 模块一：课程引言与行业背景 (Slide 1 - Slide 10)
**教学目标**：铺垫大语言模型带来的行业变革，引入智能旅游业务痛点。

- **Slide 1**: 【封面】企业级智能旅游推荐智能体(Agent)平台实战
- **Slide 2**: 【自我介绍/讲师介绍】课程目标与适用人群
- **Slide 3**: 【行业背景】从传统 OTA(携程/去哪儿) 到基于 LLM 的个性化旅游代理
- **Slide 4**: 【传统旅游规划的痛点】信息超载、攻略碎片化、预算难以统筹
- **Slide 5**: 【新技术破局】生成式 AI 如何重构人机交互界面
- **Slide 6**: 【什么是智能体应用(AI Agent)】不是简单的聊天，而是具备感知、记忆、工具使用与行动能力的数字实体
- **Slide 7**: 【本项目的宏伟愿景】支持千万级用户、百万并发的超大规模 Multi-Agent 商业级系统
- **Slide 8**: 【课程大纲预览】六大核心模块(理论+实战架构)
- **Slide 9**: 【为什么选择全栈/多语言】对比不同语言在企业架构中的天职(Python做AI/Go做并发/Java做枢纽)
- **Slide 10**: 【本章小结】前沿技术大爆发下的工程师机遇

---

## 模块二：基础架构知识普及：语言与业务底座 (Slide 11 - Slide 25)
**教学目标**：为学生梳理 Java、Go、Python 三种现代后端语言的核心特性及其在系统中的角色。

- **Slide 11**: 【章节页】构建现代企业架构的基石
- **Slide 12**: **[基础知识]** 后端语言之王：Java 与 Spring 体系生态
- **Slide 13**: **[基础知识]** Spring Cloud Gateway 响应式网关的作用与工作原理
- **Slide 14**: **[基础知识]** 并发王者：Go 语言的设计哲学
- **Slide 15**: **[图表]** 线程(Thread) vs 协程(Goroutine) 内存模型对比 
- **Slide 16**: **[基础知识]** Go 中的 CSP 模型：通道(Channel)与并发等待组(WaitGroup)
- **Slide 17**: **[基础知识]** 拥抱AI：Python 生态与多进程(Uvicorn)模型
- **Slide 18**: **[基础框架]** RPC 与 HTTP 演进：从单体服务到微服务集群
- **Slide 19**: **[基础框架]** 服务注册与发现机制：为什么我们需要 Nacos 和 Etcd？
- **Slide 20**: **[机制探究]** Nacos 是如何做心跳检测与服务保护的？
- **Slide 21**: **[基础知识]** 微服务配置中心的作用与灰度发布概念
- **Slide 22**: **[基础知识]** 什么是云原生(Cloud Native)：Docker 与 K8s 简介
- **Slide 23**: **[基础知识]** Docker 隔离级别与网络模型
- **Slide 24**: **[思考题]** 如果让你设计一个高并发API，如何组合使用上述语言与技术？
- **Slide 25**: 【本章小结】合理发挥技术栈特长，没有最好，只有最适合

---

## 模块三：基础架构知识普及：海量存储与高并发 (Slide 26 - Slide 40)
**教学目标**：向学生普及高并发（大几十万并发）下的数据持久化、分库分表与多级缓存体系机制。

- **Slide 26**: 【章节页】应对 “微博热搜级” 并发流量的数据阵型
- **Slide 27**: **[基础知识]** 一次请求背后的数据 I/O 旅程 (内存 > 固态 SSD > 网线跨机房)
- **Slide 28**: **[挑战]** 传统单台关系型数据库(MySQL)的性能瓶颈
- **Slide 29**: **[解决方案]** “库表拆分”理论：分库(Sharding)与按Hash路由
- **Slide 30**: **[利器]** 中间件 ShardingSphere / 分布式TiDB的透明代理技术
- **Slide 31**: **[设计模式]** CQRS (命令和查询责任分离) 架构图解
- **Slide 32**: **[基础知识]** NoSQL 与 Redis 高速缓存为什么这么快？(内存+单线程Reactor模型)
- **Slide 33**: **[高频安全问题]** 缓存三兄弟：什么是缓存穿透？如何解决(布隆过滤器)
- **Slide 34**: **[高频安全问题]** 缓存三兄弟：什么是缓存击穿？什么是缓存雪崩(引入随机TTL)
- **Slide 35**: **[限流降级]** 保命机制：基于 Redis 滑动窗口的 API 限流策略
- **Slide 36**: **[基础知识]** RAG 与向量数据库：Milvus 如何理解文本相关性？
- **Slide 37**: **[存储分离]** 对象存储(OSS/S3) 与 CDN 加速：图片资源的大胃王
- **Slide 38**: **[可靠性]** 异步解耦神器：Kafka 消息队列简介
- **Slide 39**: **[存储矩阵总结]** Polyglot Persistence (多语言混合持久化策略全景图)
- **Slide 40**: 【本章小结】1次写、十万次读：大厂技术演进的主旋律

---

## 模块四：系统核心业务分析与总体重构设计 (Slide 41 - Slide 55)
**教学目标**：将上述的技术理论落地，详细展现该智能旅游系统从需求到架构大图的过程。

- **Slide 41**: 【章节页】解构系统：核心业务流与系统边界
- **Slide 42**: 【系统需求提取】用户全流程故事板 (User Story)
- **Slide 43**: 【组件拆分模型】多角色拆分：Gateway -> Manager -> Workers -> Ranks
- **Slide 44**: 【系统架构设计大图 v1.0】全栈语言组合架构呈现
- **Slide 45**: 【A2A 机制图】Agent-To-Agent 内部协议解析（解决异步推拉）
- **Slide 46**: 【MCP 协议集成】什么是 MCP(Model Context Protocol) 及其对标准 API 的意义
- **Slide 47**: 【网关层的职责】展示 Spring Cloud Gateway 如何进行 JWT 和恶意意图拦截
- **Slide 48**: 【Spring AI 登场】在 Java 层实现的前置Advisor过滤(Prompt检查)
- **Slide 49**: 【Agent层】Supervisor Agent 的任务编排能力(生成旅行大纲与分块)
- **Slide 50**: 【技能挂载】Skill Loader 的插件化设计（家庭包、省钱包、豪华包）
- **Slide 51**: 【分工协作】RouteMaking 与 TripPlanner 双Agent工作流图解
- **Slide 52**: 【性能后盾】Go-Fanout 服务的网络扇出演示（同时查询10家酒店接口）
- **Slide 53**: 【性能后盾】Go-Ranker 重排引擎的漏斗降级模型(快速计算性价比得分)
- **Slide 54**: 【安全钩子】Go-Policy 的 OPA(Open Policy Agent) 检查（防刷策略）
- **Slide 55**: 【本章小结】用企业视角看待整体架构分层设计

---

## 模块五：核心代码剖析——Agent与表现层实战 (Slide 56 - Slide 70)
**教学目标**：逐行代码分析 Python 端的复杂异步调度及数据落地方法。

- **Slide 56**: 【章节页】走进心脏：Agent编排核心代码剖析
- **Slide 57**: 【代码拆解】Agent 调度入口 `app.py` 的 Uvicorn 生命周期
- **Slide 58**: 【实战：A2A协议定义】`a2a/protocol.py` 中的 Topic 与 Inbox 模型
- **Slide 59**: 【状态长记忆】Memory 模块：InMemory 与 VectorStore 记忆流加载
- **Slide 60**: 【大模型交互】LangChain/OpenAI Client 接入，设定 System Prompt
- **Slide 61**: 【异步数据持久化】如何通过 `SQLAlchemy` 使用 `aiomysql` 落库
- **Slide 62**: 【实战：SQLAlchemy】`TripPlanRepo` 下的异步写入(`session.commit()`)
- **Slide 63**: 【实战：Redis 接入】`cache_manager.py` 下的全局高可用缓存实例
- **Slide 64**: 【缓存随机降雪崩】如何在 `set_hot_destination_plan` 加入 `fuzzed_ttl`
- **Slide 65**: 【前端交互体系】表现层 Vue3/Vite SPA 体系接入流程
- **Slide 66**: 【小程序适配】微信小程序对于 Agent 对话栈的 WebSocket/长轮询渲染
- **Slide 67**: 【防篡改体系】微服务间的通信调用签名校验 `X-Internal-Signature` 机制
- **Slide 68**: 【接口幂等性】解决网路多重重试：IdempotencyKey 的生成与控制
- **Slide 69**: 【流式响应】Agent 打字机效果的底层 SSE 协议实现
- **Slide 70**: 【本章小结】如何高效编写并发安全的 IO 代码

---

## 模块六：云原生部署、稳定性打流与项目升华 (Slide 71 - Slide 100)
**教学目标**：真实生产环境的部署监控、压测试验以及 Etcd/Nacos 高级迁移。

- **Slide 71**: 【章节页】从开发机走向服务器：生产环境保卫战
- **Slide 72**: 【容灾迁移】Nacos 与 Etcd 之间如何做到双写平滑替换？
- **Slide 73**: 【代码实战】通过 `ENVIRONMENT` 分解双栈客户端启动行为
- **Slide 74**: 【压测演练】并发5000+： Locust 压测脚本 (`stress/load_test.py`) 解析
- **Slide 75**: 【数据对比分析】灰度放量中发现的不一致性与修复 (`canary-etcd-migration...`)
- **Slide 76**: 【容器化演进】项目的 `docker-compose.yml` 配置文件全景
- **Slide 77**: 【全链路追踪】什么是 OpenTelemetry？追踪一次跨三语言的请求
- **Slide 78**: 【TraceID 演示】在 Java Gateway, Python Agent, Go Ranker 间透传头部
- **Slide 79**: 【监控看盘】Prometheus 数据抓取与 Grafana 大盘配置
- **Slide 80**: 【告警机制】如何定义告警阈值以及接入企业微信/飞书Webhook
- **Slide 81 - 85**: 【实战案例回顾】从第一行代码到集群部署的完整总结串讲 (5张回顾图表)
- **Slide 86 - 93**: 【大学期末答辩/开源项目扩展】基于本项目还能做哪些大作业课题(例如：引入知识图谱、加设社交属性模块等)
- **Slide 94 - 98**: 【行业反思】面对多 Agent 的“推理幻觉库”，如何通过外网工具进一步强化置信度？
- **Slide 99**: 【问答环节 Q&A】欢迎同学们提问与交流探讨
- **Slide 100**: 【结束页】感谢聆听！扫码获取项目代码仓库与课件资源。

