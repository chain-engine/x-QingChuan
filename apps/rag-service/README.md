# 晴川 rag-service（qingchuan-rag）

人社（HRSS）数据离线索引 + RAG（检索增强生成）一体化服务平台。
人社领域知识，检索可答 —— 内置离线同步流水线，对外提供 HTTP + MCP 双协议检索与问答能力，由观海（x-GuanHai）工程改造而来。

[English](README.en.md) | 中文

![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104%2B-009688?logo=fastapi&logoColor=white)
![MCP](https://img.shields.io/badge/MCP-2.3%2B-24292F)
![ChromaDB](https://img.shields.io/badge/ChromaDB-0.4%2B-F97316)
![sentence-transformers](https://img.shields.io/badge/sentence--transformers-5.7%2B-FF6F61)
![BM25](https://img.shields.io/badge/BM25-Incremental%20Index-2C3E50)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0%2B-D71F00?logo=sqlalchemy&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-8.0-4479A1?logo=mysql&logoColor=white)
![APScheduler](https://img.shields.io/badge/APScheduler-3.10%2B-2C3E50)
![Docker](https://img.shields.io/badge/Docker-24.0%2B-2496ED?logo=docker&logoColor=white)
![uv](https://img.shields.io/badge/uv-0.5%2B-6E40C9)

![Stars](https://img.shields.io/github/stars/chain-engine/x-QingChuan?label=Stars)
![Forks](https://img.shields.io/github/forks/chain-engine/x-QingChuan?label=Forks)
![License](https://img.shields.io/github/license/chain-engine/x-QingChuan?label=License)
![Commits](https://img.shields.io/github/commit-activity/m/chain-engine/x-QingChuan?label=Commits)

## 💡 项目介绍

晴川（x-QingChuan）项目的人社数据离线索引 + RAG 一体化服务平台，默认监听 `:8010`，核心能力：

- **HTTP + MCP 双出口**：HTTP REST API（`/api/v1`）+ MCP Streamable HTTP（`/mcp`），Agent / IDE / 工具均可接入；
- **人社数据离线同步**：内置 APScheduler 周期调度（`SYNC_CRON` 默认每日 03:00）+ HTTP 触发接口 + CLI（`qingchuan-pipeline`），将人社系统数据周期同步进向量库（Chroma，可选 Milvus）与业务库（MySQL）；
- **RAG 全链路**：文档管理（上传 / 删除）→ 文本切分 → Embedding（BAAI/bge-m3）→ 混合检索（向量 + BM25 + MMR 重排）→ LLM 生成（带引用来源）；
- **多模型生成**：OpenAI 兼容协议，支持 DeepSeek / 豆包 / 阿里云百炼 / 小米 MiMo；
- **审计与限流**：所有写操作写入审计日志（操作人固定 `internal`），内置 slowapi 限流。

**当前状态**：RAG 检索流水线已端到端跑通；BM25 采用自研增量倒排索引（增删 O(词数)，不再全量重建）；文本切分支持 recursive / character / token / semantic（自研 SemanticSplitter）等策略；人社同步支持 mock 数据联调（`HRSS_MOCK=true` 默认开启）。

## 🚀 快速开始

### 🖥️ 1. 环境要求

- **Windows / Linux / macOS** 全平台支持；需要 Python 3.12+；
- **uv** 包管理器（工作区依赖同步必需）：<https://docs.astral.sh/uv/>；
- **Docker / Docker Compose**（容器部署需要；本地开发可选用）；
- **MySQL 8.0**（生产推荐；本地开发可用 SQLite，如 `sqlite:///./data/qingchuan.db`）。

### 📥 2. 项目代码克隆

```bash
git clone https://github.com/chain-engine/x-QingChuan.git
cd x-QingChuan/apps/rag-service
```

### 📦 3. 依赖同步安装

在仓库根目录执行：

```bash
uv lock                 # 首次运行：生成锁文件
uv sync --package qingchuan-rag  # 仅安装 rag-service 及其工作区依赖
```

### ⚙️ 4. 环境配置

复制示例文件并按需调整（`.env` 与 `config.yaml` 两种方式均支持，环境变量优先）：

```bash
cp .env.example .env
# 或
cp config.yaml.example config.yaml
```

核心参数说明：

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `SERVER_HOST` / `SERVER_PORT` | `0.0.0.0` / `8010` | HTTP 监听地址与端口（MCP 挂载于 `/mcp`） |
| `DATABASE_URL` | `mysql+pymysql://yeyushilai:123456@localhost:3306/qingchuan` | 业务库（审计日志 / 同步任务状态）；本地可 SQLite |
| `SYNC_ENABLED` / `SYNC_CRON` | `false` / `0 3 * * *` | 人社周期同步开关与 cron 表达式 |
| `SYNC_BATCH_SIZE` / `SYNC_INCREMENTAL` | `100` / `true` | 每批拉取条数 / 默认增量同步 |
| `HRSS_API_URL` / `HRSS_API_TOKEN` | 空 | 人社数据源地址与 Bearer Token（生产必填） |
| `HRSS_MOCK` / `HRSS_MOCK_COUNT` | `true` / `5` | mock 模式：无真实 API 时使用本地示例数据端到端联调 |
| `EMBEDDING_MODEL` | `BAAI/bge-m3` | 向量嵌入模型（本地离线推理） |
| `VECTOR_STORE_TYPE` / `VECTOR_STORE_PERSIST_DIR` | `chroma` / `./data/chroma` | 向量库类型（chroma / milvus）与持久化目录 |
| `TEXT_SPLITTER_PROVIDER` / `TEXT_SPLITTER_STRATEGY` | `langchain` / `recursive` | 文本切分实现（langchain / llamaindex）与策略（recursive / character / token / semantic；chunk_size 512 / overlap 50） |
| `RETRIEVAL_TOP_K` / `RETRIEVAL_SIMILARITY_THRESHOLD` | `5` / `0.7` | 检索数量 / 相似度阈值（`RETRIEVAL_USE_MMR` 控制 MMR） |
| `GENERATION_PROVIDER` / `GENERATION_MODEL` | `mimo` / `mimo-v2.6-pro` | 生成模型；支持 DeepSeek / 豆包 / 阿里云百炼 / 小米 MiMo |
| `DEEPSEEK_API_KEY` / `DOUBAO_API_KEY` / `ALIYUN_API_KEY` / `MIMO_API_KEY` | 空 | 各 LLM 供应商 API Key（生产必填） |
| `RATE_LIMIT_ENABLED` | `false` | slowapi 限流开关（每分钟 / 每小时配额） |
| `CORS_ENABLED` / `CORS_ALLOW_ORIGINS` / `CORS_ALLOW_CREDENTIALS` | `true` / `localhost:3000,8080` / `true` | 跨域开关、允许来源与凭证；允许来源含 `*` 时自动关闭凭证；生产环境禁止 `*` |

### 🚀 5. 服务启动

**本地开发热重载启动**（在 `apps/rag-service` 目录执行；热重载跟随 `DEBUG` 配置）：

```bash
uv run qingchuan-rag-api                # 默认启动：监听 / 端口取配置
uv run qingchuan-rag-api --reload       # 显式开启热重载（修改代码自动重启）
uv run qingchuan-rag-api --port 8010    # 覆盖监听端口
# 或直接使用 uvicorn
uv run uvicorn qingchuan_rag.main:app --reload --host 0.0.0.0 --port 8010
```

**Docker 容器部署**（仓库根目录执行；向量库默认 Chroma 本地持久化，零外部依赖；如切 Milvus：先 `docker compose --profile milvus up -d` 起内置三件套并设 `VECTOR_STORE_TYPE=milvus`）：

```bash
docker compose up --build rag-service
```

### 🧪 6. 常用工程命令

```bash
uv run ruff check .            # 静态代码检查（对齐 x-GuanHai 规则）
uv run ruff format .           # 代码格式化
uv run pytest                  # 单元 / 集成 / API 测试（tests/ 目录）
pre-commit run --all-files     # pre-commit 钩子（ruff --fix + ruff-format）
uv audit                       # 依赖漏洞扫描（uv 0.5+ 内置）
```

### 💬 7. 使用方法示例

**RAG 问答**：

```bash
curl -X POST http://127.0.0.1:8010/api/v1/rag/query \
  -H "Content-Type: application/json" \
  -d '{"query": "社会保险缴费基数如何确定？"}'
```

**仅检索不生成**：

```bash
curl -X POST http://127.0.0.1:8010/api/v1/rag/retrieve \
  -H "Content-Type: application/json" \
  -d '{"query": "养老保险待遇领取条件", "top_k": 5}'
```

**触发人社数据同步**：

```bash
uv run qingchuan-pipeline sync --full
# 或调用 HTTP 接口
curl -X POST http://127.0.0.1:8010/api/v1/sync/trigger \
  -H "Content-Type: application/json" \
  -d '{"full": true}'
```

**MCP 接入**：MCP 客户端示例见 `scripts/qingchuan_mcp_client.py`，HTTP 客户端示例见 `scripts/qingchuan_http_client.py`。

### ❓ 8. 常见问题排查

| 症状 | 解决方案 |
| --- | --- |
| 端口被占用 | 修改 `SERVER_PORT`（或启动参数 `--port`） |
| `uv` 安装失败 / 超时 | 检查网络；本服务内置阿里云 PyPI 镜像（`[tool.uv.index]`），或配置代理 |
| Windows 上报 torch `shm.dll` 缺失 | 保持锁定版本 `torch==2.12.0`，不要升级到 2.14.x |
| 数据库连接失败 | 确认 MySQL 已启动且数据库已创建（`utf8mb4`）；本地可改用 SQLite |
| 人社同步返回 401 / 超时 | 联调期间保持 `HRSS_MOCK=true`；接真实 API 时配置 `HRSS_API_URL` / `HRSS_API_TOKEN` 并关闭 mock |
| 启动报配置错误 | 非法配置会阻断启动（validate）；`TEXT_SPLITTER_SEPARATORS` 等复杂参数请通过 `config.yaml` 配置 |

## 📁 项目结构

```text
apps/rag-service/
├── src/qingchuan_rag/
│   ├── main.py                 # FastAPI 入口（HTTP 路由 + /mcp Streamable HTTP 双挂载）
│   ├── cli.py                  # CLI：qingchuan-rag-api（HTTP 启动器，支持 --reload/--port/--workers）
│   ├── http_server/            # HTTP 网关（v1：health / rag / document / sync / audit）
│   ├── mcp_server/             # MCP 网关（server 装配 / tools 工具 / prompts 提示词 / resources 资源）
│   ├── sync/                   # 人社数据同步（scheduler 调度器 / sync_service 同步服务）
│   ├── services/               # 业务服务（document / rag / sync / retrieval_adapter / audit）
│   ├── repositories/           # 数据仓储（document / vector / bm25 / sync_task / audit_log）
│   ├── rag/                    # RAG 流水线（retrieval / augmentation / generation / pipeline）
│   ├── retrieval/              # 混合检索（candidate 召回 / ranking 重排 / understanding 查询理解）
│   ├── infras/                 # 基础设施（database / vector / embedding / chunking / storage / bm25 / llm / http / hrss）
│   ├── models/                 # ORM 实体（audit_logs / sync_tasks）
│   ├── schemas/                # 请求 / 响应 Schema
│   ├── constants/              # 常量与枚举（API 前缀 / 默认参数 / 支持文档类型）
│   ├── core/                   # 核心基础设施（config / logger / exceptions / middleware）
│   └── utils/                  # 工具（相似度 / 过滤 / 索引优化）
├── tests/                      # 单元 / 集成 / API 测试
├── scripts/                    # HTTP / MCP 客户端示例脚本
├── data/                       # 运行数据（chroma / bm25 / documents / db）
├── .env.example                # 环境变量配置模板
├── config.yaml.example         # YAML 配置模板
├── Dockerfile                  # 容器镜像（uv sync --package qingchuan-rag）
└── pyproject.toml              # qingchuan-rag（入口：qingchuan-rag-api / qingchuan-pipeline）
```

## 🏗️ 系统架构

### 🧱 分层架构

```mermaid
flowchart TB
    subgraph CLIENTS["客户端"]
        A1["HTTP 客户端（REST）"]
        A2["MCP 客户端（Agent / IDE / 工具）"]
    end

    subgraph GATEWAY["网关层（:8010）"]
        B1["HTTP 网关（/api/v1）"]
        B2["MCP 网关（/mcp Streamable HTTP）"]
    end

    subgraph SERVICE["服务层（services/）"]
        C1["RAG 服务（query / retrieve / embed）"]
        C2["文档服务（上传 / 删除 / 索引）"]
        C3["同步服务（人社数据）"]
        C4["审计服务（写操作留痕）"]
    end

    subgraph CORE["核心流水线"]
        D1["RAG 流水线（retrieval / augmentation / generation）"]
        D2["混合检索（向量 + BM25 + MMR）"]
    end

    subgraph INFRA["基础设施"]
        E1[("MySQL 业务库")]
        E2[("Chroma / Milvus 向量库")]
        E3[("BM25 稀疏索引")]
        E4["LLM Provider（OpenAI 兼容）"]
        E5["人社数据源（API）"]
    end

    A1 --> B1
    A2 --> B2
    B1 --> C1
    B1 --> C2
    B1 --> C3
    B2 --> C1
    C1 --> D1
    D1 --> D2
    C2 --> D2
    C3 --> C2
    C2 --> C4
    C3 --> C4
    C1 --> C4
    D2 --> E2
    D2 --> E3
    C2 --> E1
    C3 --> E1
    C3 -. "离线同步" .-> E5
    D1 --> E4
```

### 🔄 核心业务流程

**人社数据离线同步 → 在线问答**：

```mermaid
flowchart LR
    subgraph OFFLINE["离线索引流水线"]
        S1["人社数据同步<br/>(CLI / APScheduler / HTTP 触发)"] --> S2["文本切分<br/>(langchain recursive)"]
        S2 --> S3["向量化（bge-m3）"]
        S3 --> S4["向量库 Chroma + BM25 索引"]
        S1 --> S5["同步任务状态<br/>(MySQL sync_tasks)"]
    end

    subgraph ONLINE["在线问答"]
        Q1["用户问题"] --> Q2["混合检索<br/>(向量 + BM25 + MMR)"]
        Q2 --> Q3["增强与重排"]
        Q3 --> Q4["LLM 生成（带来源）"]
        Q4 --> Q5["返回答案"]
    end

    S4 -.-> Q2
```

**写操作审计留痕**：

```mermaid
flowchart LR
    W["写操作<br/>(文档上传 / 删除、同步触发)"] --> A["AuditService"]
    A --> L["audit_logs 表<br/>(操作人固定 internal)"]
    Q["审计查询接口（只读）"] --> L
```

### 🔩 关键技术组件

| 模块 | 组件 | 说明 |
| --- | --- | --- |
| Web 框架 | FastAPI + Uvicorn | HTTP 网关，统一响应包装与异常处理 |
| MCP | mcp 2.3+ | Streamable HTTP（/mcp），只读检索工具 |
| 向量检索 | ChromaDB + sentence-transformers（BAAI/bge-m3） | 稠密索引；`VECTOR_STORE_TYPE` 可选 Milvus |
| 稀疏检索 | BM25IndexStore（自研增量倒排） | 倒排表 + Okapi BM25 打分，增删 O(词数) 增量维护，与向量检索混合；rank-bm25 仅一致性对比与备用路径 |
| 混合检索 | candidate + ranking + understanding | 多路召回（向量 / BM25 / 关键词）+ 重排（MMR / RRF / 分数过滤）+ 查询理解（意图 / 实体 / 扩写 / 改写） |
| 文本切分 | langchain-text-splitters + 自研 SemanticSplitter + llama-index-core | recursive / character / token / semantic（BGE-M3 语义断点）/ llamaindex 策略 |
| 业务库 | SQLAlchemy 2 + PyMySQL（MySQL 8） | 审计日志 / 同步任务状态 |
| 周期调度 | APScheduler | 人社同步 cron（默认每日 03:00） |
| LLM 接入 | langchain-openai（OpenAI 兼容） | DeepSeek / 豆包 / 阿里云百炼 / 小米 MiMo |
| 限流 | slowapi | 每分钟 / 每小时配额 |
| 配置 | pydantic + PyYAML + python-dotenv | `.env` 与 `config.yaml` 双通道，非法配置阻断启动 |
| 日志 | loguru | 彩色控制台 / 文件轮转（1 天 / 保留 7 天） |
| 工程化 | uv + ruff + pre-commit + pytest | 工作区依赖、静态检查、测试 |

## 🛠️ 技术栈

| 分类 | 选型 |
| --- | --- |
| 开发语言 | Python 3.12+ |
| Web 框架 | FastAPI 0.104+ / Uvicorn 0.24+ |
| MCP | mcp 2.3+（Streamable HTTP） |
| 向量数据库 | ChromaDB 0.4+（可选 Milvus 2.4 / milvus-lite） |
| 向量嵌入 | sentence-transformers 2.2+（BAAI/bge-m3，本地离线推理） |
| 稀疏检索 | 自研 BM25 增量倒排（rank-bm25 0.2+ 备用 / 对比） |
| 文本切分 | langchain-text-splitters 1.1+ / llama-index-core 0.14+ / 自研 SemanticSplitter |
| LLM 接入 | langchain-core 0.3+ / langchain-openai 0.2+ / openai 1.0+（OpenAI 兼容协议） |
| 业务数据库 | MySQL 8.0（SQLAlchemy 2 + PyMySQL；本地可 SQLite） |
| 周期调度 | APScheduler 3.10+ |
| 限流 | slowapi 0.1+ |
| 配置管理 | pydantic 2.5+ / PyYAML / python-dotenv |
| 日志 | loguru 0.7+ |
| 包管理 | uv（workspace 成员 qingchuan-rag / qingchuan-domain） |
| 工程化 | ruff + pre-commit + pytest（pytest-asyncio / pytest-cov / pytest-mock） |
| 部署 | Docker / Docker Compose |

## 📡 API 文档说明

服务开启 **Swagger 交互式文档 / ReDoc 只读文档 / OpenAPI JSON**：

| 文档 | 访问地址 |
| --- | --- |
| Swagger | <http://127.0.0.1:8010/docs> |
| ReDoc | <http://127.0.0.1:8010/redoc> |
| OpenAPI JSON | <http://127.0.0.1:8010/openapi.json> |
| MCP 端点 | <http://127.0.0.1:8010/mcp>（Streamable HTTP） |

### 📋 核心 API 接口清单（/api/v1）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/health` | 健康检查（向量库 / 文档库状态） |
| GET | `/api/v1/version` | 版本信息 |
| GET | `/api/v1/status` | 系统运行状态（uptime / 向量数 / 文档数） |
| POST | `/api/v1/rag/query` | RAG 问答（检索 + 生成，支持 top_k / 阈值 / MMR / 元数据过滤 / 指定 provider） |
| POST | `/api/v1/rag/retrieve` | 仅检索不生成（返回片段与来源） |
| POST | `/api/v1/rag/embed` | 文本向量化 |
| GET | `/api/v1/rag/stats` | RAG 系统统计 |
| POST | `/api/v1/documents/upload` | 上传文档并自动索引（支持 UTF-8 / GBK 编码） |
| GET | `/api/v1/documents` | 文档列表（分页，可按状态 / 类型过滤） |
| GET | `/api/v1/documents/{document_id}` | 文档详情 |
| DELETE | `/api/v1/documents/{document_id}` | 删除文档及其向量 |
| GET | `/api/v1/documents/{document_id}/status` | 文档处理状态 |
| POST | `/api/v1/sync/trigger` | 触发人社同步（默认增量；`full=true` 全量，`force=true` 强制重跑） |
| GET | `/api/v1/sync/status` | 最近一次同步状态 |
| GET | `/api/v1/sync/status/{task_id}` | 按任务 ID 查询同步状态 |
| GET | `/api/v1/audit/logs` | 审计日志列表（按实体 / 操作 / 操作者 / 时间范围 / 关键字分页） |
| GET | `/api/v1/audit/logs/{log_id}` | 审计日志详情 |

### 🔧 MCP 工具（只读）

| 工具 | 说明 |
| --- | --- |
| `retrieve_docs` | 检索与查询最相关的知识片段（支持 top_k / 相似度阈值 / MMR / 元数据过滤），返回 `{"items": [...]}` 稳定结构 |
| `rag_query` | 基于知识库内容生成完整回答（检索 → 增强 → 生成），返回答案与引用片段 |

### 🔐 权限与访问控制

- 内部服务，不设应用鉴权；所有写操作（文档上传 / 删除、同步触发）经 **AuditService** 写入审计日志，操作人固定为 `internal`，审计查询接口只读；
- 内置 **slowapi 限流**（`RATE_LIMIT_ENABLED`，默认每分钟 60 次 / 每小时 1000 次）；
- 配置非法直接阻断启动；生产环境建议 `DEBUG=false` 并收紧 CORS 白名单。

## 💾 存储配置说明

| 存储 | 用途 | 配置参数 | 备注 |
| --- | --- | --- | --- |
| MySQL 8.0 | 审计日志 / 同步任务状态 | `DATABASE_URL` | 生产必需；本地可 SQLite（`sqlite:///./data/qingchuan.db`）；数据库需提前创建（`utf8mb4`） |
| Chroma 向量库 | 稠密向量索引（文档向量） | `VECTOR_STORE_TYPE=chroma`、`VECTOR_STORE_PERSIST_DIR=./data/chroma`、`VECTOR_STORE_COLLECTION_NAME=documents`、`VECTOR_STORE_DISTANCE=cosine` | **默认选型**：本地持久化，零外部依赖；Milvus 可选（`uv sync --extra milvus` + `VECTOR_STORE_TYPE=milvus` + `VECTOR_STORE_MILVUS_URI`） |
| BM25 索引 | 稀疏检索索引（增量倒排，关键词匹配） | `./data/bm25/default.json`（index_name 默认 `default`） | 增删 O(词数) 增量维护；快照式落盘（默认每 50 次变更落盘一次 + shutdown 落盘） |
| 文档存储 | 上传的源文档 | `./data/documents` | DocumentRepository 存储路径 |
| 日志文件 | loguru 文件轮转 | `LOG_FILE_PATH` / `LOG_ROTATION=1 day` / `LOG_RETENTION=7 days` | 按天轮转 / 保留 7 天 |

数据结构定义（ORM 实体）：

- `audit_logs`：操作人（operator_id）/ 操作（action）/ 对象（entity_type / entity_id）/ 结果（result）/ 时间戳 / 备注；
- `sync_tasks`：任务类型（type）/ 状态（status）/ 批次（batch）/ 成功失败计数 / 时间戳。

## 📄 许可证

[MIT 许可证](../LICENSE) © 2026 ChainEngine

## 📚 参考资料

- Python: <https://www.python.org/>
- uv: <https://docs.astral.sh/uv/>
- FastAPI: <https://fastapi.tiangolo.com/>
- Uvicorn: <https://www.uvicorn.org/>
- MCP（Model Context Protocol）: <https://modelcontextprotocol.io/>
- ChromaDB: <https://docs.trychroma.com/>
- sentence-transformers: <https://www.sbert.net/>
- rank-bm25: <https://github.com/dorianbrown/rank_bm25>
- langchain-text-splitters: <https://python.langchain.com/>
- SQLAlchemy: <https://www.sqlalchemy.org/>
- PyMySQL: <https://pymysql.readthedocs.io/>
- APScheduler: <https://apscheduler.readthedocs.io/>
- slowapi: <https://github.com/laurentS/slowapi>
- pydantic: <https://docs.pydantic.dev/>
- loguru: <https://loguru.readthedocs.io/>
- Docker: <https://docs.docker.com/>

## 📮 联系方式

- **作者**：John Young（夜雨诗来）
- **邮箱**：john.young@foxmail.com
- **Gitee**：<https://gitee.com/yeyushilai>
- **GitHub**：<https://github.com/yeyushilai>
- **项目地址**：<https://github.com/chain-engine/x-QingChuan>
