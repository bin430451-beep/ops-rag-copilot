# 部署操作手册
## 前置条件
- Linux x86_64，Docker 24+，Docker Compose v2
- GPU 节点：NVIDIA Driver 535+，nvidia-container-toolkit
- 磁盘：模型缓存预留 ≥ 60 GB；数据盘挂载到 `/data`
- 网络：内网可访问模型服务端口；Nginx 8080 端口仅对内网开放
## 在线部署步骤
### 1. 准备配置
```bash
cp .env.example .env
vi .env   # 修改 API_KEYS、ALLOWED_IPS、模型服务地址
```
### 2. 拉起模型服务（GPU）
```bash
docker compose --profile gpu up -d embedding reranker llm
docker compose logs -f llm   # 等待 "Uvicorn running"
```
### 3. 拉起核心服务
```bash
docker compose up -d qdrant backend nginx
make init-collection
curl -s http://localhost:8080/healthz
```
### 4. 冒烟测试
```bash
curl -X POST http://localhost:8080/api/v1/kb/upload \
  -H "X-API-Key: $API_KEY" \
  -F "file=@docs/sample.md" -F "dept=public"
curl -X POST http://localhost:8080/api/v1/chat/query \
  -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"question":"Nginx 502 如何排查？"}'
```
### 5. 配置告警接入
监控系统 Webhook 指向：
```
POST http://<host>:8080/api/v1/ops/analyze-alert
Header: X-API-Key: <key>
Body: {"alert": "...", "logs": "..."}
```
## CPU 演示模式（无 GPU）
无 GPU 环境可用 Ollama 快速体验完整链路（Chat + Embedding 均由 Ollama 提供）：

```bash
# 1. 启动 Ollama 并拉取模型
docker compose --profile cpu up -d ollama
docker compose exec ollama ollama pull qwen2.5:7b

# 2. .env 中切换到 CPU 配置：
#    LLM_BASE_URL=http://ollama:11434/v1
#    LLM_MODEL=qwen2.5:7b
#    EMBEDDING_BASE_URL=http://ollama:11434/v1
#    RERANK_ENABLED=false

# 3. 拉起核心服务
docker compose up -d qdrant backend nginx
make init-collection
```

说明：CPU 模式关闭 Reranker（无轻量 CPU 重排替代），检索退化为向量序 + BM25 混合，
功能链路完整，适合功能演示与项目验收。
## 离线 / 信创内网部署
运行时无外联；首次部署需准备离线包（镜像 + 模型权重）。
1. 打包机（有网）：`docker save` 导出镜像 + `hf download` 拉模型权重
2. 生成 `opsrag-offline-vX.Y.Z.tar.gz`，拷入内网
3. 内网执行 `docker load -i *.tar` → 改 `.env` → `docker compose up -d`
## 常见问题
| 现象 | 排查 |
| --- | --- |
| 403 forbidden | 检查 `ALLOWED_IPS` 与 Nginx `geo` 段 |
| 401 | `X-API-Key` 不在 `API_KEYS` 列表 |
| 上传报 unsupported | 文件后缀需在 `.txt/.md/.pdf/.docx` |
| 检索无结果 | 确认 `make init-collection` 已执行 |
| Rerank 报错 | 检查 `RERANK_URL` 是否为 TEI 的 `/rerank` 路径 |
