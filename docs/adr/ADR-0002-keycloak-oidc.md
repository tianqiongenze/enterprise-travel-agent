# ADR-0002: 鉴权采用 Keycloak OIDC 全栈（资源服务器模式）

- 状态：Accepted（2026-09-19，用户决策）
- 背景：原实现无端到端鉴权，内部签名仅取 SHA-256 前 16 位且密钥硬编码。
- 决策：Gateway 引入 spring-boot-starter-oauth2-resource-server，校验
  Keycloak（realm=travel）签发的 RS256 JWT；`travel.security.mode=oauth2`
  在 dev/staging/prod 环境模板强制开启，本地与单测可显式 `off`（门禁在
  staging/prod 档位拒绝 off/none）。Gateway→Runtime 保留服务间信任：
  HMAC-SHA256 全量签名并绑定 clientId。Runtime `api/auth.py` 具备独立
  JWKS 验签能力（oidc 模式下端到端校验用户身份）。
- 后果：引入一套有状态中间件（Compose/local k8s 已含）；演示账号仅限
  教学环境；未来可平滑切换为云 IAM（同 OIDC 协议）。
