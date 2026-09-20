# 真 Embedding 验证报告（Gap3）

日期：2026-09-20　分支：`gap/3-spring-ai-embedding`　工作树：`.worktrees/gap3-springai`

## 结论

| 项 | 结果 | 证据 |
|---|---|---|
| Python embedding 回归 | ✅ 27 passed | `tests/test_embedding_providers.py` + `tests/test_embedding_real_contract.py` + `tests/test_llm_rationale.py`（pytest，2.31s） |
| DashScope 线协议契约（本地假服务器，无外网） | ✅ 4/4 | `tests/test_embedding_real_contract.py`：Bearer 鉴权头、`{"model","input":{"texts"},"parameters":{"dimension","text_type":"query"}}` 请求体、维度校验、HTTP 401 报错、缺 key 报错 |
| HashEmbeddingProvider 基线 | ✅ PASS | `scripts/verify_real_embedding.py` 输出 |
| DashScope 真实调用 | ⏸️ SKIP（诚实跳过） | 本机未配置 `AI_DASHSCOPE_API_KEY`/`DASHSCOPE_API_KEY`，脚本按设计不伪造结果 |
| Java 网关单测 | ✅ 23/23 | `mvn -o test -Dprotoc.skip=true`（本机离线仓库；protoc 生成步骤在本机有 ZIP SLIP 兼容问题，用主检出目录已生成的 stub 编译，CI 全量跑 protoc） |

## 复现

```bash
# Python（worktree 根目录）
env PYTHONPATH="$PWD/services/techgroup-enterprise-travel-runtime" \
  python -m pytest tests/test_embedding_providers.py tests/test_embedding_real_contract.py tests/test_llm_rationale.py -q
env PYTHONPATH="$PWD/services/techgroup-enterprise-travel-runtime" python scripts/verify_real_embedding.py

# Java（X: 为 subst 的仓库根，规避中文路径 protobuf 工具链乱码）
cd services/techgroup-enterprise-travel-gateway
mvn -o test -Dprotoc.skip=true
```

## 真 Key 一次跑通说明

设置环境变量后重跑脚本即出 PASS（脚本自动写 `stress/embedding_verification_report.json` + sha256 sidecar）：

```bash
export AI_DASHSCOPE_API_KEY=sk-xxx   # 或 DASHSCOPE_API_KEY
python scripts/verify_real_embedding.py   # verdict 应为 PASS
```

- 请求线协议（`POST <endpoint>`，`Authorization: Bearer <key>`，`parameters.text_type=query`，维度默认 1024，可由 `TRAVEL_EMBEDDING_DIM` 覆盖）已由本地假服务器的契约测试逐字段锁定。
- 后端选择链：`TRAVEL_EMBEDDING_BACKEND=auto` → 本地 sentence_transformers → dashscope（有 key）→ Hash（带告警），保证无 key 环境可降级运行。

## 诚实边界

- 本机未配置 DashScope key，真实调用未执行；报告为 SKIP 而非 PASS，未伪造。
- 本机 protoc 通过 Maven 生成 stub 存在中文路径兼容问题，Java 测试用主检出目录的已生成 stub 编译通过（`-Dprotoc.skip=true`）；CI（Linux 全 ASCII 路径）跑完整 `mvn test` 无需此开关。
