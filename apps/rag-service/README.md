# 晴川 rag-service（x-QingChuan RAG 服务）

晴川（x-QingChuan）项目的人社数据离线索引 + RAG（检索增强生成）一体化服务，
由观海（x-GuanHai）工程照搬改造而来。

## 能力

- **HTTP + MCP 双出口**：HTTP REST API（`/api/v1`）+ MCP Streamable HTTP（`/mcp`）
- **人社数据离线同步**：内置 APScheduler 周期调度 + HTTP 触发接口，
  将人社系统数据按周期同步进向量数据库（Chroma）与业务库（MySQL）
- **RAG 全链路**：文档管理（上传/删除）→ 切分 → Embedding → 向量检索 → 重排增强 → LLM 生成
- **审计**：所有操作写入审计日志（操作人固定 `internal`）

## 快速开始

```bash
# 1. 安装依赖（workspace 根目录执行）
uv sync --package qingchuan-rag

# 2. 配置环境变量
cp .env.example .env   # 按需修改 DATABASE_URL / SYNC_* / HRSS_*

# 3. 启动 HTTP 服务（默认 8010）
uv run uvicorn qingchuan_rag.main:app --host 0.0.0.0 --port 8010

# 4. 触发人社数据同步
uv run qingchuan-pipeline sync --full
# 或调用 HTTP 接口
# POST /api/v1/sync/trigger  {"full": true}
```

## 目录结构

```
src/qingchuan_rag/
├── http_server/      # HTTP 出口（v1/rag、v1/document、v1/sync、v1/audit_log、v1/health）
├── mcp_server/       # MCP 出口（server/tools）
├── sync/             # 人社同步编排（scheduler 调度器 / sync_service 同步服务）
├── services/         # 业务服务（document/rag/sync/retrieval_adapter/audit）
├── repositories/     # 数据仓储（document/vector/bm25/sync_task/audit_log）
├── rag/              # RAG 流水线（retrieval/augmentation/generation/pipeline）
├── retrieval/        # 检索（向量/BM25 混合）
├── infras/           # 基础设施（database/vector/embedding/chunking/storage/bm25/llm/http/hrss）
│   ├── http.py       # 通用 HTTP 请求能力（RequestsHttpProvider）
│   └── hrss.py       # 人社（社保）平台服务接口层（薄封装，依赖 http.py）
├── models/           # ORM 实体（audit_logs/sync_tasks）
└── cli.py            # API 进程入口（qingchuan-rag-api）
```

## 约定

- 领域协议层（Schema / 端口 / 常量 / 异常）统一在 `packages/domain`（`qingchuan_domain`）维护
- 默认数据库 `mysql+pymysql://yeyushilai:123456@localhost:3306/qingchuan`
- 向量库 Chroma，持久化目录 `data/chroma`
- 人社数据源接口层为 `infras/hrss.py`：拿到真实对接文档后，调整端点路径、
  返回字段解析与认证方式（TODO 已标注），并配置 `HRSS_MOCK=false` + `HRSS_API_URL` 即可联调
- 未配置真实人社 API 前默认 `HRSS_MOCK=true`，用本地示例数据端到端调试同步链路
