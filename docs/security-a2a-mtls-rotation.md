# A2A 内部模式、mTLS 与内部密钥轮换（Gap1）

本文覆盖三个互相咬合的内部安全收口：`/a2a/*` 仅内部访问门禁、本地 mTLS 证书生成与可选 TLS 启动、内部 HMAC 共享密钥的双窗口轮换。

## 1. A2A 内部模式（`TRAVEL_A2A_INTERNAL_ONLY=true`）

默认关闭，行为与历史版本一致。开启后（Python runtime 侧，`src/travel_agent/api/app.py`）：

- `/a2a/send`、`/a2a/inbox/{receiver}` 要求三个内部头：
  - `X-Internal-Client-Id`：必须等于 `TRAVEL_INTERNAL_CLIENT_ID`（默认 `techgroup-enterprise-travel-gateway`）；
  - `X-A2A-Scope`：send 时为调用方自带头，inbox 时服务端合成为 `inbox.{receiver}`（防止签名重放到别的收件箱）；
  - `X-Internal-Signature`：`HMAC-SHA256(scope + "." + clientId, shared_secret)` 的 hex 小写。
- 校验失败抛 `PermissionError` → HTTP 401。
- 网关侧（Java）已在请求转发时带上 client-id + 签名（`PythonRuntimeClient` / `InternalTokenService`），A2A 流量经由网关即可透明通过。

契约测试：`tests/test_a2a_internal_mode.py`（6 例，覆盖关/开/错签/错 client/合法/旧密钥窗口）。

## 2. mTLS / TLS

- 本地证书生成：`platform/deploy/security/gen_dev_certs.py`，用 openssl 生成自签 CA + 服务端证书（SAN 含 `localhost`、`travel-agent-api`、`travel-gateway`、`127.0.0.1`）+ 客户端证书（CN=travel-gateway-client），落盘 `var/certs/`（已加入 `.gitignore`，永不入库）。
- 可选 TLS 启动：`Dockerfile.travel-agent-api` 的 CMD 已改为条件判断——设置了 `TRAVEL_TLS_CERT` 与 `TRAVEL_TLS_KEY` 时 uvicorn 以 `--ssl-certfile/--ssl-keyfile` 启动，否则明文启动。K8s 生产侧仍建议走 ingress TLS 终结。
- 网关侧若需调用端 mTLS，可在 Java `application.yml` 的 ssl 段挂 `var/certs/client.*`（staging/prod 由证书管理器下发，不在本仓库硬编码）。

## 3. 内部密钥双窗口轮换

### 方案

- 签名算法（双端逐字节一致）：`hex(HMAC-SHA256(payload + "." + clientId, secret))`。
  - Python：`src/travel_agent/security.py::make_internal_signature` / `verify_internal_signature`。
  - Java：`services/techgroup-enterprise-travel-gateway/.../InternalTokenService.java`，新增 `verify()` 并支持旧密钥回退。
- 双窗口：轮换期同时配置
  - `TRAVEL_INTERNAL_SHARED_SECRET`（新密钥，签发用）
  - `TRAVEL_INTERNAL_SHARED_SECRET_PREVIOUS`（旧密钥，仅验签回退）
  runtime 与网关都先验当前密钥、再验旧密钥；窗口关闭（清空 PREVIOUS）后旧密钥立即失效。

### 操作步骤（`platform/deploy/security/rotate_internal_secret.py`）

1. **Phase 1**：`python platform/deploy/security/rotate_internal_secret.py --current-env platform/deploy/env/prod.env`
   - 脚本生成 256 位 CSPRNG 新密钥，把旧值写入 `PREVIOUS`，新值写入当前键；demo 占位密钥会拒绝执行（exit 2）。
2. **发布顺序**：先重启 runtime（Python），再重启 gateway（Java）。因为 runtime 双验签在先，任意顺序都安全，runtime 先行是文档约定。
3. **Phase 2（关窗）**：全部 pod 上线后执行 `--close-window`，清空 `PREVIOUS`，旧密钥失效。
4. k8s/生产环境通过 secret 管理系统下发 env，密钥不进仓库、不硬编码。

### 验证

- 窗口内旧密钥签名可过、关窗后即拒：`tests/test_secret_rotation.py`（5 例）。
- A2A 门禁在旧密钥窗口内仍可用：`test_a2a_internal_mode.py::test_flag_on_previous_secret_window_passes`。
- Java 侧：`InternalTokenService.verify()` 先当前后旧密钥（逻辑与 Python 对齐，单测留在 CI 跑）。
