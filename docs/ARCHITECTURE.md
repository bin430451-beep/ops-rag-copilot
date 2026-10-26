# 架构说明
## 分层
| 层 | 组件 | 职责 |
| --- | --- | --- |
| 接入层 | Nginx | TLS 终止（可选）、IP 白名单、反向代理 |
| 应用层 | FastAPI | 鉴权、路由、RAG 编排、Agent 编排 |
| 模型层 | vLLM / TEI | Chat、Embedding、Reranker（OpenAI / TEI 兼容协议） |
| 存储层 | Qdrant + SQLite | 向量库 + 文档元数据 |
| 外部系统 | 监控系统 / Webhook | 告警源 |
## RAG 流水线
1. **解析**：`ingest.parse_file` 支持 PDF / DOCX / MD / TXT
2. **切分**：`splitter.split_text` 递归字符切分，优先按标题 / 段落 / 句号
3. **向量化**：`embedder.embed_texts` 批量调用 Embedding 服务
4. **入库**：`retriever.upsert_chunks` 写入 Qdrant，payload 含 doc_id / dept / chunk_index
5. **检索**：`retriever.search` 向量召回 Top-K（可带 dept 过滤）
6. **重排**：`reranker.rerank` 调用 bge-reranker-v2-m3，失败自动降级为向量序
7. **生成**：`llm.chat` 结合 Prompt 模板生成答案，失败返回兜底话术 + 原文
## 降级策略
| 故障点 | 降级行为 |
| --- | --- |
| Reranker 超时/异常 | 使用向量召回顺序，日志 WARN |
| LLM 不可用 | 返回 `FALLBACK_MESSAGE` + 检索原文 |
| Qdrant 不可用 | `/readyz` 返回 degraded；问答返回空知识提示 |
| Embedding 不可用 | 上传失败并返回明确错误 |
## 扩展点
- 混合检索：在 `retriever.search` 中加入 BM25 召回并做 RRF 融合
- 多租户：payload 增加 `tenant_id`，检索时强制过滤
- 流式输出：`/chat/query` 增加 SSE 分支，复用 `LLMClient.stream`
