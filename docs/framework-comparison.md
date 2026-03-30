# 企业级智能体框架对比（旅游推荐场景）

## 候选框架

- AgentScope-AI
- OneAgent（此处按 Dynatrace OneAgent 理解，为观测代理而非编排框架）
- LangGraph
- Spring AI Alibaba
- JoyAgent（JD）

## 结论（先给答案）

对于“分布式大规模 + MCP + Skills”的企业级旅游推荐系统，推荐采用：

1. **主编排层：LangGraph 风格工作流编排**（可控状态机、可测试、可追溯）
2. **企业接入层：Spring AI Alibaba / Spring Boot**（若组织主技术栈是 Java）
3. **互操作与治理边界：MCP Gateway**（工具注册、schema、审计、权限）

当前仓库默认设置：`TRAVEL_ORCHESTRATION_ENGINE=langgraph`。

- 选择原因：LangGraph 的状态图抽象和生态成熟度在三者中更平衡。
- `AgentScope-AI`：适合多智能体快速实验与协作开发。
- `OneAgents`：可作为扩展适配器保留，按团队现网框架成熟度逐步启用。

这与 Oracle 咨询结论一致：把 MCP 作为硬边界，框架可替换；编排与企业接入分层。

## 当前项目实现状态（已更新）

- 已在 `techgroup-enterprise-travel-gateway` 中接入 **Spring AI Alibaba** 依赖：
  - `com.alibaba.cloud.ai:spring-ai-alibaba-agent-framework:1.1.2.0`
  - `com.alibaba.cloud.ai:spring-ai-alibaba-starter-dashscope:1.1.2.1`
- 已新增 `SpringAiAlibabaAdvisorService`，通过 `ChatClient.Builder` 生成推荐说明（无可用模型时自动回退本地策略文案）。
- Spring Boot 已升级到 `3.4.6`，与 Spring AI Alibaba 1.1.2.x 兼容。

## 对比维度

- 架构编排能力
- 状态管理与恢复
- MCP/工具接入
- Skills/插件扩展
- 可观测性
- 生产部署成熟度
- Java/Python 生态匹配

## 精简对比

### LangGraph

- 优势：图编排、checkpoint、复杂多Agent流程控制强
- 局限：企业治理与组织级平台能力需配套补齐
- 适合：复杂推理链路与可回放调试

### Spring AI Alibaba

- 优势：Java 企业生态友好，便于接入现有 Spring 微服务体系
- 局限：复杂图编排细粒度能力通常不如 LangGraph 原生图工具
- 适合：企业生产落地与治理体系整合

### AgentScope-AI

- 优势：多Agent开发体验好，Runtime/Studio 能力完整
- 局限：在你组织里是否“生产标准件”取决于团队技术栈与运维体系
- 适合：快速多Agent研发与实验到生产过渡

### JoyAgent（JD）

- 优势：端到端多Agent产品化思路，治理能力有亮点
- 局限：需评估与现有平台集成成本及长期演进锁定
- 适合：快速构建多Agent业务产品

### OneAgent（Dynatrace）

- 优势：可观测性强
- 局限：不是Agent编排框架
- 适合：作为运行态观测层，与编排框架组合使用

## 参考链接（用于课程与项目文档引用）

- AgentScope-AI: https://doc.agentscope.io/
- AgentScope GitHub: https://github.com/agentscope-ai/agentscope
- LangGraph: https://www.langchain.com/langgraph
- Spring AI Alibaba: https://github.com/alibaba/spring-ai-alibaba
- Spring AI Alibaba Docs: https://java2ai.com/en/docs/1.0.0.2/tutorials/graph/quick-guide/
- JoyAgent JDGenie: https://github.com/jd-opensource/joyagent-jdgenie
- JOYA: https://github.com/JoyAgents-AI/JOYA
- Dynatrace OneAgent: https://www.dynatrace.com/platform/oneagent
