# ADR-0003: maxAgentSteps/maxToolCalls 在执行期强制（ExecutionBudget）

- 状态：Accepted（2026-09-19）
- 背景：原实现仅在请求校验阶段检查下限，执行期从不限量——控制参数是摆设。
- 决策：新增 `orchestration/budget.py` ExecutionBudget，经 contextvar 传播；
  MCP 注册表在每次工具调用时消费 tool 预算，编排引擎每个阶段消费 agent
  step 预算；超限抛 BudgetExceeded，由 API 层映射为 4xx。A2A worker 的
  基础设施级数据访问不占用调用方 MCP 预算（多智能体各自预算属后续工作）。
- 后果：推荐请求的资源上限成为硬约束；预算快照进入事件流
  （recommend.budget_snapshot）供容量分析。
