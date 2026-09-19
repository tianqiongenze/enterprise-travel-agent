# ADR-0005: 语义检索采用可插拔双后端 embedding（本地 bge + DashScope）

- 状态：Accepted（2026-09-19，用户决策）
- 背景：原 FAISS/Qdrant/Milvus 后端共用 SHA-256 词桶哈希向量，属 token
  重叠冒充语义检索。
- 决策：`memory/embeddings.py` 提供三档 provider：local-model（默认首选，
  BAAI/bge-small-zh-v1.5，离线教学环境）、dashscope（配置 API Key 即切
  云端）、hash（仅显式 fallback，启动时打告警并暴露 provider_name 供
  go-live 门禁校验——staging/prod 拒绝 hash 与未配置的 auto）。维度由
  TRAVEL_EMBEDDING_DIM 声明，建索引前确定。
- 后果：教学环境零外网可用；生产必须安装本地模型或配 Key；Milvus
  memory_key 严格校验防表达式注入。
