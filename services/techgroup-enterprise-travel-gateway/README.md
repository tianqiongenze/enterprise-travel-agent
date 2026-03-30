# TechGroup Enterprise Travel Gateway

企业入口服务（Spring Boot）：

- 统一接收外部请求
- 执行策略校验（工具白名单、步数与调用限额）
- 调用 Python Agent Runtime 的内部接口
- 可选审计镜像到 Pulsar

## 运行

```bash
mvn spring-boot:run
```

默认端口：`8080`

## 测试

本模块已将 Surefire 升级到 `3.5.4`，用于修复 JUnit 5.12+ 的 `OutputDirectoryProvider not available` 测试发现异常。

```bash
mvn test
```

## API 概览

- `GET /api/v1/travel/health`
- `GET /api/v1/travel/policy/cache/stats`
- `POST /api/v1/travel/recommend`

响应中新增：

- `aiRationale`（由 Spring AI Alibaba ChatClient 生成）

请求需包含：

- tenantId/userId/policyId/conversationId/idempotencyKey
- city/days/budget/travelers/preferences
- maxAgentSteps/maxToolCalls/allowedTools

## 文档

- 开发者 API 文档：`services/techgroup-enterprise-travel-gateway/docs/api-developer.md`
- 用户 API 文档：`services/techgroup-enterprise-travel-gateway/docs/api-user.md`
- 平台功能说明书：`docs/platform-product-spec.md`

## Spring AI Alibaba 依赖

- `com.alibaba.cloud.ai:spring-ai-alibaba-agent-framework:1.1.2.2`
- `com.alibaba.cloud.ai:spring-ai-alibaba-starter-dashscope:1.1.2.2`

配置（`application.yml`）：

```yaml
spring:
  ai:
    dashscope:
      api-key: ${AI_DASHSCOPE_API_KEY:}
```
