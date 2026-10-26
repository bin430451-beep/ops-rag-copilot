# OpsRAG Copilot
> 企业私有云智能运维与 RAG 知识协作平台 · 100% 内网部署 · 数据不出域
![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688)
![Qdrant](https://img.shields.io/badge/VectorDB-Qdrant-red)
![License](https://img.shields.io/badge/License-MIT-green)
## 背景
企业内网环境下，运维团队面临三个痛点：
- **数据安全红线**：运维日志、SOP 不能出内网，无法使用 SaaS 大模型
- **排障依赖人工经验**：常见告警处理流程分散在个人经验里，新人上手慢
- **文档检索低效**：历史手册散落在 Wiki / 共享盘，关键词搜索命中率低
本项目在信创私有云环境中搭建了一套 **"大模型 + RAG + 运维辅助"** 的协作平台，
所有组件开源、数据本地化，通过 IP 白名单 + API Key 双重管控。
## 架构
```mermaid
flowchart LR
    U[运维/业务用户] -->|内网 HTTPS| NG[Nginx<br/>反向代理 + IP 白名单]
    NG --> BE[FastAPI Backend]
    BE -->|Embedding| EM[Qwen3-Embedding]
    BE -->|向量检索| QD[(Qdrant)]
    BE -->|Rerank| RK[bge-reranker-v2-m3]
    BE -->|Chat| LLM[Qwen / DeepSeek]
    BE -->|元数据| SQ[(SQLite)]
    BE -->|告警分析| MON[监控系统 Webhook]
```
## 核心能力
| 能力 | 说明 |
| --- | --- |
| 私有化部署 | Docker Compose 编排 Qdrant / Embedding / Reranker / LLM / Backend / Nginx |
| RAG 知识库 | 多格式解析（PDF/Word/MD/TXT）+ 递归切分 + 向量化 + Reranker 重排 |
| 混合检索 | 向量召回 + BM25 关键词召回，RRF 融合，长尾命中增强 |
| 文档管理 | 前端可视化：文档列表 / 审核 / 删除 |
| 运维 Agent | 告警 → Prompt 模板 → 日志提取 → 初步分析，对接任意监控 Webhook |
| Agent 编排 | Function Calling 工具调用（知识库/日志/时间/文档清单）+ 多轮会话记忆 |
| 流式问答 | SSE 逐字输出（/chat/stream），失败自动降级兜底话术 |
| 可观测性 | X-Request-ID 全链路透传 + 结构化访问日志（方法/路径/状态/耗时） |
| 访问控制 | IP 白名单中间件 + API Key 鉴权 + 文档审核接口 |
| 降级兜底 | 大模型不可用时自动返回"检索原文 + 兜底话术"，保证可用性 |
## 项目定位
本项目**不训练任何模型、不重复造轮子**，核心价值在于**开源组件的调用、集成、搭建与部署落地**：

- 通过 **OpenAI 兼容协议**调用 Qwen / DeepSeek 推理服务（vLLM / Ollama 部署）
- 使用 **TEI** 部署 Embedding / Reranker 模型服务
- 使用 **Qdrant** 作为向量检索后端
- FastAPI 仅做轻量**编排网关**，将各组件串成可落地的业务闭环

适合作为企业内网"大模型 + RAG + 运维辅助"的**集成实施样板**，开箱可部署、可交付、可验收。
## 技术栈
- **LLM**：Qwen2.5-14B / DeepSeek（vLLM / Ollama 部署）
- **Embedding**：Qwen3-Embedding-0.6B（TEI）
- **Reranker**：bge-reranker-v2-m3（TEI）
- **向量库**：Qdrant
- **后端**：FastAPI + httpx + SQLite
- **网关**：Nginx（反向代理 + IP 白名单）
- **部署**：Docker Compose，支持离线镜像 + 模型挂载
## 关键设计
- **检索精度优化**：向量召回 Top-20 → Reranker 精排 Top-5，解决长文档检索不准与大模型幻觉
- **降级策略**：Reranker 超时自动退化为向量序；LLM 不可用返回原文 + 兜底话术
- **权限隔离**：文档 payload 带 `dept` 字段，检索时强制过滤，实现部门级知识隔离
- **双层白名单**：Nginx `geo` + 后端中间件双校验，防止绕过代理
## 目录结构
```
backend/app/rag      # 切分 / 向量化 / 检索 / 重排
backend/app/agent    # 告警分析 Agent + Prompt 模板
backend/app/core     # 鉴权 / IP 白名单 / LLM 客户端
deploy/nginx         # 反向代理配置
docs/                # 架构 / 部署 / 用户 SOP
```
## 快速演示（Demo）
> 完整流程：拉起服务 → 上传示例文档 → 知识库问答。
> 模型服务（Embedding / Reranker / LLM）需 GPU 节点或已就绪的模型端点；无 GPU 时仍可演示「降级兜底」能力。

```bash
cp .env.example .env
docker compose --profile gpu up -d embedding reranker llm   # 拉起模型服务
docker compose up -d qdrant backend nginx                   # 拉起核心服务
make init-collection                                        # 初始化向量集合
```

浏览器访问 `http://<host>:8080`，按界面引导：

1. 输入 API Key（默认 `dev-key`，生产务必修改）
2. 上传示例文档 `docs/sample.md`（含 Nginx 502 / Oracle 表空间 / K8s CrashLoopBackOff / Fastjson 漏洞等常见 SOP）
3. 提问，例如：
   > Nginx 返回 502，上游是 Java 服务，如何排查？

命令行冒烟测试：

```bash
# 上传示例文档
curl -X POST http://localhost:8080/api/v1/kb/upload \
  -H "X-API-Key: dev-key" \
  -F "file=@docs/sample.md" -F "dept=public"

# 知识库问答
curl -X POST http://localhost:8080/api/v1/chat/query \
  -H "X-API-Key: dev-key" -H "Content-Type: application/json" \
  -d '{"question":"Oracle 表空间满了怎么办？"}'

# 告警分析（对接监控 Webhook）
curl -X POST http://localhost:8080/api/v1/ops/analyze-alert \
  -H "X-API-Key: dev-key" -H "Content-Type: application/json" \
  -d '{"alert":"K8s Pod CrashLoopBackOff","logs":"error: context deadline exceeded"}'
```

## 部署
> 运行阶段无外联，部署阶段支持离线镜像 + 本地模型目录。
> 详细步骤见 [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)。
```bash
cp .env.example .env
docker compose up -d --build
```
## License
MIT © 2025 OpsRAG Copilot
