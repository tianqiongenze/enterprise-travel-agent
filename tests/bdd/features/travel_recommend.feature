Feature: 黄金周百万并发行程推荐（BDD，第四轮 R9）
  作为文旅平台的游客
  我需要在高峰期快速获得可信的行程推荐
  以便在人流洪峰下依然顺畅决策

  Background:
    Given 降级本地事件总线的运行时已就绪

  Scenario: 正常推荐返回完整行程骨架
    When 游客请求 "北京" 3 天推荐
    Then 响应包含 4 个核心区块
    And 城市为 "北京"

  Scenario: 空参数使用默认行程（三天北京）
    When 游客请求默认参数推荐
    Then 响应包含 4 个核心区块

  Scenario: GraphQL 查询与 REST 契约一致
    When 游客通过 GraphQL 查询 "上海" 的推荐
    Then GraphQL 返回城市 "上海" 且包含酒店列表

  Scenario: 健康面与观测面始终可用
    When 运维探测 /health、/metrics 与 /graphql/health
    Then 三个探针全部 200

  Scenario: 深度过高的 GraphQL 查询被拒绝
    When 攻击者发送 10 层嵌套查询
    Then GraphQL 返回 errors 且 data 为空
