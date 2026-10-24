# Spring AI Alibaba 下沉（Gap3）

日期：2026-09-20　分支：`gap/3-spring-ai-embedding`

## 目标

网关（Java/Spring Boot 3.5）侧真正持有 Spring AI 能力：AI 建议调用、超时与降级由网关负责，Python runtime 不再是唯一 AI 入口；embedding 侧提供真实 DashScope 验证通道。

## 变更

### 1. SpringAiAlibabaAdvisorService（重写）

- 构造依赖：`ObjectProvider<ChatClient.Builder>` + 配置 `travel.ai.advisor.enabled`（默认 true）、`travel.ai.advisor.timeout-seconds`（默认 5）。
- 核心方法：`advise(request, instruction)` 返回 `record AdvisorResult(String rationale, boolean degraded, String reason)`，**永不抛异常**。
- 降级原因枚举：`advisor-disabled` / `chat-client-unavailable` / `blank-content` / `advisor-error`（异常与超时均归此）。
- 超时实现：单 daemon 线程池 `spring-ai-advisor` + `Future.get(timeout)`，超时后 `future.cancel(true)`。
- 兼容：`buildRationale(request)` = `advise(request, null).rationale()`，老调用点无感。
- 兜底文案保留原口径（按城市/偏好/预算生成），降级结果可被上层观测。

### 2. 新端点 `POST /api/v1/travel/assistant/rewrite`

- 请求体：`AssistantRewriteRequest(@NotBlank text, String city)`。
- 语义：把自然语言诉求交给 advisor 改写；成功返回 `{traceId, rewritten, degraded:false}`；降级返回兜底文案 + `degraded:true` + `degradedReason`。
- traceId 缺省自动生成（UUID），与全链路追踪对齐。

### 3. 配置（application.yml）

```yaml
travel:
  ai:
    advisor:
      enabled: ${TRAVEL_AI_ADVISOR_ENABLED:true}
      timeout-seconds: ${TRAVEL_AI_ADVISOR_TIMEOUT_SECONDS:5}
```

### 4. 测试

- `SpringAiAlibabaAdvisorServiceTest`（7 例，纯 JUnit+Mockito 深桩 `ChatClient.Builder`，不需要 DashScope key/网络）：disabled 降级、builder 缺失降级、空内容降级、正常返回去空白、模型异常降级、慢响应超时降级（1s 超时 vs 3s 睡眠）、`buildRationale` 向后兼容。
- `TravelGatewayControllerTest` 新增 3 例：rewrite 成功载荷、降级载荷暴露 `degraded/degradedReason`、空 text 400（VALIDATION_ERROR）。
- 实测：`mvn -o test -Dprotoc.skip=true` → **Tests run: 23, Failures: 0, Errors: 0**（BUILD SUCCESS）。详见 [real-embedding-verification.md](real-embedding-verification.md)。

### 5. Embedding 下沉验证

- DashScope 线协议契约测试（本地假 HTTP 服务器，逐字段断言鉴权/请求体/维度/错误路径），见 `tests/test_embedding_real_contract.py`。
- `scripts/verify_real_embedding.py`：hash 基线恒跑；有 key 才打真实 DashScope，输出 PASS/SKIP/FAIL 结论并写 `stress/embedding_verification_report.json` + sha256。无 key 本机实测 verdict=SKIP（诚实记录）。

## 已知边界

- 本机 Maven protoc 生成存在中文路径兼容问题，Java 测试以 `-Dprotoc.skip=true` + 主检出目录已生成 stub 编译；CI Linux 路径不受影响，跑完整 `mvn test`。
- DashScope 真实网络调用待配置 key 后执行（复现命令见验证报告）。
