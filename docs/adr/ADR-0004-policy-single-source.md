# ADR-0004: policy-core.v1.json 为策略唯一事实源

- 状态：Accepted（2026-09-19）
- 背景：策略阈值与会员分级曾四处重复（rego/policy_core.go/Java/policy-core
  契约），且 policy.rego 语法错误导致 go-policy 服务从未成功启动（新测试
  曝光后已重写修复）。
- 决策：`data-contracts/policy-core/policy-core.v1.json` 为唯一上游；
  Java PolicyCoreSpec 运行时消费契约文件（TRAVEL_POLICY_CORE_FILE）；
  rego 与 Go 默认值由 `scripts/check_policy_consistency.py` 在 CI 校验与
  契约一致；金标用例（golden cases）驱动 Python 平价测试。
- 后果：策略变更 = 契约 JSON 一处修改 + CI 一致性红线；rego 语言子集限制
  （避免 future keywords 依赖）。
