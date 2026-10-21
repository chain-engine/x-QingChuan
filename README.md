# 晴川（QingChuan）

人社（HRSS）API 离线索引 + RAG 检索 + Agent 智能问答平台。
让政务领域知识可检索、可问答、可编排 —— 基于人社数据，通过 HTTP + MCP 双协议服务对外暴露，由 LangGraph 多智能体编排调度。

[English](README.en.md) | 中文

![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2%2B-1C3C3C)
![LangChain](https://img.shields.io/badge/LangChain-0.3%2B-1C3C3C?logo=langchain&logoColor=white)
![MCP](https://img.shields.io/badge/MCP-2.3%2B-24292F)
![ChromaDB](https://img.shields.io/badge/ChromaDB-0.4%2B-F97316)
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

晴川是一个面向**人社（HRSS）业务场景**的**多智能体编排 + 知识库赋能平台**。工程采用 uv monorepo 结构，包含两个可独立部署的服务与两个共享包：

- **rag-service（qingchuan-rag）**：人社数据离线索引 + RAG（检索增强生成）一体化服务，对外暴露 **HTTP + MCP 双协议**；离线索引流水线（CLI + APScheduler 周期任务）随服务内置；
- **agent-service（qingchuan-agent）**：**LangGraph 多智能体编排运行时** + HTTP 服务；顶层编排图执行 `route → subagent → aggregate`，新 Agent 在 `agents/` 目录注册即可扩展；经 MCP 工具调用 rag-service，不持有索引写权限；
- **packages/domain（qingchuan-domain）**：实体 / Schema / 检索协议 / 端口的唯一事实来源，两个服务直接引用；
- **packages/common（qingchuan-common）**：跨服务共享组件（MCP 客户端封装 / 认证 / 审计 / 可观测性，占位）。

**当前状态**：RAG 检索流水线已端到端跑通（人社同步支持 mock 数据联调）；Agent 编排骨架已交付（新业务 Agent 注册即可扩展），任务 / 事件持久化默认关闭，无数据库也可启动服务。

## 🚀 快速开始

### 🖥️ 1. 环境要求

- **Windows / Linux / macOS** 全平台支持；需要 Python 3.12+（`requires-python = ">=3.12,<3.14"`）；
- **uv** 包管理器（工作区依赖同步必需）：<https://docs.astral.sh/uv/>；
- **Docker / Docker Compose**（容器部署需要；本地开发可选用）；
- **MySQL 8.0**（生产推荐；本地开发可不依赖数据库或使用 SQLite，agent-service 持久化默认关闭）。

### 📥 2. 项目代码克隆

```bash
git clone https://github.com/chain-engine/x-QingChuan.git
cd x-QingChuan
```

### 📦 3. 依赖同步安装

```bash
uv lock                 # 首次运行：生成锁文件
uv sync --all-packages  # 安装全部工作区成员（apps/* 和 packages/*）
```

### ⚙️ 4. 环境配置

复制示例文件并按需调整（核心参数见下表）：

```bash
# rag-service：.env 与 config.yaml 两种方式均支持
cp apps/rag-service/.env.example apps/rag-service/.env
# 或
cp apps/rag-service/config.yaml.example apps/rag-service/config.yaml

# agent-service：在仓库根目录的 .env 中配置（前缀 QINGCHUAN_AGENT_）
```

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `DATABASE_URL` | `mysql+pymysql://yeyushilai:123456@localhost:3306/qingchuan` | rag-service 业务库（审计 / 同步任务）；本地可用 SQLite |
| `SYNC_ENABLED` / `SYNC_CRON` | `false` / `0 3 * * *` | 人社周期同步开关与 cron 表达式 |
| `HRSS_API_URL` / `HRSS_API_TOKEN` | 空 | 人社数据源地址与 Bearer Token（生产必填） |
| `HRSS_MOCK` | `true` | mock 模式：无真实 API 时使用本地示例数据端到端联调 |
| `EMBEDDING_MODEL` | `BAAI/bge-m3` | 向量嵌入模型（本地离线推理） |
| `VECTOR_STORE_PERSIST_DIR` | `./data/chroma` | Chroma 向量库持久化目录 |
| `GENERATION_PROVIDER` / `GENERATION_MODEL` | `mimo` / `mimo-v2.6-pro` | **rag-service 专用**生成模型；支持 DeepSeek / 豆包 / 阿里云百炼 / 小米 MiMo |
| `QINGCHUAN_AGENT_AI_LLM_API_KEY` | 空（走 Mock） | **agent-service 专用**大模型 Key（独立于 rag-service 的 `MIMO_*`） |
| `QINGCHUAN_AGENT_AI_LLM_BASE_URL` | 空 | agent-service 专用 LLM 地址（OpenAI 兼容，如 `https://api.xiaomimimo.com/v1`） |
| `QINGCHUAN_AGENT_AI_LLM_MODEL` | `deepseek-chat` | agent-service 专用模型名（如 `mimo-v2.6-pro`）；换厂商只改这三个变量 |
| `QINGCHUAN_AGENT_DATABASE_ENABLED` | `false` | agent-service 任务 / 事件持久化开关（首次启动自动建表） |
| `QINGCHUAN_AGENT_RAG_HTTP_BASE_URL` | `http://rag-service:8010` | agent-service 使用的 rag 客户端地址（本地用 `http://127.0.0.1:8010`） |

> **LLM 配置分离**：agent-service 与 rag-service 的 LLM 各自独立配置、互不读取。
> rag-service 读 `MIMO_*` / `GENERATION_*`；agent-service 只读 `QINGCHUAN_AGENT_AI_LLM_*`
> （两级嵌套字段需经 core/config.py 显式回读，OS 环境变量与 .env 均可注入，OS 优先）。
> 任一服务要换模型/厂商，只改自己那一段即可。

### 🚀 5. 服务启动

**本地开发热重载启动**：

```bash
# rag-service：HTTP 服务（默认 0.0.0.0:8010；MCP 挂载于 /mcp）
uv run --package qingchuan-rag qingchuan-rag-api
# 或
uv run --package qingchuan-rag uvicorn qingchuan_rag.main:app --reload --host 0.0.0.0 --port 8010

# agent-service：HTTP 服务（默认 127.0.0.1:8020）
uv run --package qingchuan-agent qingchuan-agent-api
# 或
uv run --package qingchuan-agent uvicorn qingchuan_agent.main:app --reload --host 127.0.0.1 --port 8020

# agent-service：编排演示（骨架占位；验证注册表 / 路由 / 运行时）
uv run --package qingchuan-agent qingchuan-agent
```

**Docker 容器部署**：

```bash
docker compose up --build
```

### 🧪 6. 常用工程命令

```bash
uv run ruff check .            # 静态代码检查
uv run ruff format .           # 代码格式化
uv run pytest                  # 单元测试（在 rag-service 目录内执行）
pre-commit run --all-files     # pre-commit 钩子（ruff --fix + ruff-format）
uv audit                       # 依赖漏洞扫描（uv 0.5+ 内置）
```

### 💬 7. 使用方法示例

**RAG 问答（rag-service HTTP）**：

```bash
curl -X POST http://127.0.0.1:8010/api/v1/rag/query \
  -H "Content-Type: application/json" \
  -d '{"query": "社会保险缴费基数如何确定？"}'
```

**触发人社数据同步**：

```bash
uv run --package qingchuan-rag qingchuan-pipeline sync --full
# 或通过 HTTP
curl -X POST http://127.0.0.1:8010/api/v1/sync/trigger \
  -H "Content-Type: application/json" \
  -d '{"full": true}'
```

**MCP 检索**：MCP 客户端示例见 `apps/rag-service/scripts/qingchuan_mcp_client.py`；HTTP 客户端示例见 `apps/rag-service/scripts/qingchuan_http_client.py`。

**提交 Agent 任务（agent-service）**：

```bash
curl -X POST http://127.0.0.1:8020/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{"task_type": "agent_a", "payload": {"query": "..."}}'
```

### ❓ 8. 常见问题排查

| 症状 | 解决方案 |
| --- | --- |
| 端口被占用 | 修改 `SERVER_PORT`（rag-service）或 `QINGCHUAN_AGENT_SERVER_PORT`（agent-service） |
| `uv` 安装失败 / 超时 | 检查网络；rag-service 内置阿里云 PyPI 镜像，或可在根 `pyproject.toml` 添加 `[tool.uv.index]` |
| Windows 上报 torch `shm.dll` 缺失 | 保持锁定版本 `torch==2.12.0`，不要升级到 2.14.x |
| 数据库连接失败 | 确认 MySQL 已启动且数据库已创建（`utf8mb4`）；agent-service 可关闭 `QINGCHUAN_AGENT_DATABASE_ENABLED` 无库启动 |
| 人社同步返回 401 / 超时 | 联调期间保持 `HRSS_MOCK=true`；接真实 API 时配置 `HRSS_API_URL` / `HRSS_API_TOKEN` 并关闭 mock |
| 启动报配置错误 | 非法配置会阻断启动（validate）；生产环境拒绝 DEBUG / `*` CORS / memory checkpoint |

## 📁 项目结构

```text
x-QingChuan/
├── apps/
│   ├── agent-service/                  # Agent 编排运行时 + HTTP 服务（独立部署，:8020）
│   │   ├── src/qingchuan_agent/
│   │   │   ├── main.py                 # FastAPI 入口（lifespan / 中间件 / 异常 / 路由）
│   │   │   ├── cli.py                  # CLI：qingchuan-agent（演示）/ qingchuan-agent-api
│   │   │   ├── api/                    # API 层：/api/v1（health / version / agents / tasks / events）
│   │   │   ├── services/               # 业务逻辑层（AgentTaskService 全生命周期）
│   │   │   ├── repositories/           # 数据访问层（任务 / 事件仓储）
│   │   │   ├── models/                 # ORM 实体（AgentTask / AgentEvent）
│   │   │   ├── schemas/                # 请求 / 响应 Schema（ApiResponse / Page 包装）
│   │   │   ├── agents/                 # 编排层：orchestrator / registry / runtime / base / state / routing / tools
│   │   │   ├── infras/                 # 基础设施（MySQL Provider / LLM Provider / 事件总线）
│   │   │   ├── core/                   # 核心基础设施（config / logger / exceptions / middleware）
│   │   │   ├── constants/              # 常量与枚举包
│   │   │   ├── templates/              # Prompt 模板（LLM 路由提示词）
│   │   │   └── utils/                  # 工具（IP 提取 / 掩码）
│   │   ├── Dockerfile
│   │   └── pyproject.toml              # qingchuan-agent
│   └── rag-service/                    # RAG 服务：HTTP + MCP 双协议（独立部署，:8010）
│       ├── src/qingchuan_rag/
│       │   ├── main.py                 # FastAPI 入口（HTTP 路由 + /mcp Streamable HTTP）
│       │   ├── cli.py                  # CLI：qingchuan-rag-api / qingchuan-pipeline
│       │   ├── http_server/            # HTTP 网关（v1：health / rag / document / sync / audit）
│       │   ├── mcp_server/             # MCP 网关（server / tools / prompts / resources）
│       │   ├── sync/                   # 人社数据同步（scheduler 调度器 / sync_service 同步服务）
│       │   ├── services/               # 业务服务（document / rag / sync / retrieval_adapter / audit）
│       │   ├── repositories/           # 数据仓储（document / vector / bm25 / sync_task / audit_log）
│       │   ├── rag/                    # RAG 流水线（retrieval / augmentation / generation / pipeline）
│       │   ├── retrieval/              # 混合检索（candidate 召回 + ranking 重排 + understanding 理解）
│       │   ├── infras/                 # 基础设施（database / vector / embedding / chunking / storage / bm25 / llm / http / hrss）
│       │   ├── models/                 # ORM 实体（audit_logs / sync_tasks）
│       │   ├── schemas/                # 请求 / 响应 Schema
│       │   └── core/                   # 核心基础设施（config / logger / exceptions / middleware）
│       ├── tests/                      # 单元 / 集成 / API 测试
│       ├── scripts/                    # HTTP / MCP 客户端脚本（qingchuan_http_client.py / qingchuan_mcp_client.py）
│       ├── data/                       # 运行数据（chroma / bm25 / documents / db）
│       ├── Dockerfile
│       └── pyproject.toml              # qingchuan-rag
├── packages/
│   ├── common/                         # 跨服务共享组件（MCP 客户端 / 认证 / 审计 / 可观测性，占位）
│   │   └── src/qingchuan_common/
│   └── domain/                         # 共享领域包（实体 / Schema / 检索协议 / 端口，唯一事实来源）
│       └── src/qingchuan_domain/
├── docker-compose.yml                  # 一键编排 rag-service + agent-service
├── pyproject.toml                      # uv 工作区根（members：apps/*、packages/*）
├── .env                                # 环境配置（不入库）
├── .pre-commit-config.yaml             # pre-commit 钩子（ruff）
├── LICENSE                             # MIT 许可证
├── README.md / README.en.md            # 中英双语文档
└── uv.lock                             # 依赖锁文件
```

## 🏗️ 系统架构

### 🧱 分层架构

```mermaid
flowchart TB
    subgraph CLIENTS["客户端"]
        A1["HTTP 客户端（REST）"]
        A2["MCP 客户端（Agent / IDE / 工具）"]
    end

    subgraph AGENT["agent-service（qingchuan-agent，:8020）"]
        B1["API 层（/api/v1）"]
        B2["服务层（services/）"]
        B3["Agent 编排层（agents/）"]
        B4["数据访问层（repositories/）"]
    end

    subgraph RAG["rag-service（qingchuan-rag，:8010）"]
        C1["HTTP 网关（/api/v1）"]
        C2["MCP 网关（/mcp）"]
        C3["服务层（services/）"]
        C4["仓储层（repositories/）"]
    end

    subgraph INFRA["基础设施"]
        D1[("MySQL 业务库")]
        D2[("Chroma 向量库")]
        D3[("BM25 稀疏索引")]
        D4["LLM Provider（OpenAI 兼容）"]
        D5["人社数据源（API）"]
    end

    A1 --> B1
    A2 --> C2
    B1 --> B2
    B2 --> B3
    B3 -- "MCP 工具调用" --> C2
    B3 --> B4
    B4 --> D1
    C1 --> C3
    C2 --> C3
    C3 --> C4
    C4 --> D1
    C4 --> D2
    C4 --> D3
    C3 --> D4
    C3 -. "离线同步" .-> D5
```

### 🔄 核心业务流程

**Agent 编排流程（route → subagent → aggregate）**：

```mermaid
flowchart LR
    START["提交任务"] --> ROUTE["route 节点<br/>(注册表显式路由 / llm / hybrid)"]
    ROUTE -->|"已注册 Agent"| SUB["subgraph 节点<br/>(业务 Agent：MCP 检索 → LLM 生成)"]
    SUB --> AGG["aggregate<br/>(合并事件与结果)"]
    AGG --> END["返回任务结果"]
    ROUTE -->|"未注册 / 路由失败"| FAIL["任务失败（回写错误）"]
    FAIL --> END
    SUB -. "interrupt（人工接管）" .-> WAIT["等待人工<br/>(resume 继续)"]
    WAIT --> SUB
```

**RAG 离线同步 + 在线问答**：

```mermaid
flowchart LR
    subgraph OFFLINE["离线索引流水线"]
        S1["人社数据同步<br/>(CLI / APScheduler / HTTP 触发)"] --> S2["文本切分"]
        S2 --> S3["向量化（bge-m3）"]
        S3 --> S4["向量库 Chroma + BM25 索引"]
    end

    subgraph ONLINE["在线问答"]
        Q1["用户问题"] --> Q2["混合检索<br/>(向量 + BM25 + MMR)"]
        Q2 --> Q3["增强与重排"]
        Q3 --> Q4["LLM 生成（带来源）"]
        Q4 --> Q5["返回答案"]
    end

    S4 -.-> Q2
```

### 🔩 关键技术组件

| 模块 | 组件 | 说明 |
| --- | --- | --- |
| Web 框架 | FastAPI + Uvicorn | 两个服务的 HTTP 网关，统一响应包装与异常处理 |
| Agent 编排 | LangGraph | 顶层编排图 + 嵌套业务子图，interrupt / resume |
| 注册 / 路由 | AgentRegistry | task_type → AgentSpec 映射表路由，惰性编译缓存 |
| LLM 接入 | LangChain（OpenAI 兼容） | DeepSeek / 豆包 / 阿里云百炼 / 小米 MiMo |
| MCP | mcp 2.3+ | rag-service Streamable HTTP（/mcp）；agent 经 MCP 客户端调用 |
| 向量检索 | ChromaDB + sentence-transformers（BAAI/bge-m3） | 稠密索引，持久化于 `data/chroma` |
| 稀疏检索 | rank-bm25 | BM25 索引，与向量检索混合 |
| 业务库 | SQLAlchemy 2 + PyMySQL（MySQL 8） | 审计日志 / 同步任务 / Agent 任务与事件 |
| 周期调度 | APScheduler | 人社同步 cron（默认每日 03:00） |
| 配置 | pydantic-settings / pydantic + PyYAML | 分段带前缀配置；非法配置阻断启动 |
| 日志 | loguru | 彩色控制台 / 文件轮转（1 天 / 保留 7 天） |
| 工程化 | uv + ruff + pre-commit + pytest | 工作区依赖、静态检查、测试 |
| 部署 | Docker Compose | 一键编排 rag-service + agent-service |

## 🛠️ 技术栈

| 分类 | 选型 |
| --- | --- |
| 开发语言 | Python 3.12+ |
| Web 框架 | FastAPI 0.115+ / Uvicorn 0.30+ |
| Agent 编排 | LangGraph 0.2+（顶层图 + 业务子图，interrupt / resume） |
| LLM 接入 | LangChain（langchain-core 0.3+ / langchain-openai 0.2+，OpenAI 兼容协议） |
| MCP | mcp 2.3+（Streamable HTTP） |
| 向量数据库 | ChromaDB 0.4+ |
| 向量嵌入 | sentence-transformers（BAAI/bge-m3） |
| 稀疏检索 | rank-bm25 0.2+ |
| 业务数据库 | MySQL 8.0（SQLAlchemy 2 + PyMySQL；本地可 SQLite） |
| 周期调度 | APScheduler 3.10+ |
| 配置管理 | pydantic-settings 2.5+ / pydantic 2.9+ / PyYAML |
| 日志 | loguru 0.7+ |
| 包管理 | uv（工作区：apps/* + packages/*，uv.lock） |
| 工程化 | ruff + pre-commit + pytest（pytest-asyncio / pytest-cov） |
| 部署 | Docker / Docker Compose |

## 📡 API 文档说明

两个服务均开启 **Swagger 交互式文档 / ReDoc 只读文档 / OpenAPI JSON**：

| 服务 | Swagger | ReDoc | OpenAPI JSON | MCP 端点 |
| --- | --- | --- | --- | --- |
| rag-service（:8010） | <http://127.0.0.1:8010/docs> | <http://127.0.0.1:8010/redoc> | <http://127.0.0.1:8010/openapi.json> | <http://127.0.0.1:8010/mcp>（Streamable HTTP） |
| agent-service（:8020） | <http://127.0.0.1:8020/docs> | <http://127.0.0.1:8020/redoc> | <http://127.0.0.1:8020/openapi.json> | —（经 MCP 客户端调用 rag-service） |

### 📋 核心 API 接口清单

**agent-service（/api/v1，共 9 个）**：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/health` | 健康检查（含 DB / Agent 运行时状态） |
| GET | `/api/v1/version` | 版本信息 |
| GET | `/api/v1/agents/specs` | 已注册 Agent 规格 |
| POST | `/api/v1/tasks` | 提交 Agent 任务（显式 task_type 路由 / 留空 → LLM 动态路由） |
| GET | `/api/v1/tasks` | 任务列表（分页） |
| GET | `/api/v1/tasks/{task_id}` | 任务详情 |
| POST | `/api/v1/tasks/{task_id}/resume` | 人工接管：恢复被中断的任务 |
| GET | `/api/v1/events` | 协作事件列表（分页） |
| GET | `/api/v1/events/{event_id}` | 协作事件详情 |

**rag-service（/api/v1，核心子集）**：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/health` / `/version` / `/status` | 健康 / 版本 / 系统状态 |
| POST | `/api/v1/rag/query` | RAG 问答（检索 + 生成） |
| POST | `/api/v1/rag/retrieve` | 仅检索不生成（返回片段与来源） |
| POST | `/api/v1/rag/embed` | 文本向量化 |
| GET | `/api/v1/rag/stats` | RAG 系统统计 |
| POST | `/api/v1/documents/upload` | 上传文档并自动索引 |
| GET | `/api/v1/documents` | 文档列表（分页） |
| GET | `/api/v1/documents/{document_id}` | 文档详情 |
| DELETE | `/api/v1/documents/{document_id}` | 删除文档及其向量 |
| GET | `/api/v1/documents/{document_id}/status` | 文档处理状态 |
| POST | `/api/v1/sync/trigger` | 触发人社同步（默认增量；`full=true` 全量） |
| GET | `/api/v1/sync/status` | 最近一次同步状态 |
| GET | `/api/v1/sync/status/{task_id}` | 按任务 ID 查询同步状态 |
| GET | `/api/v1/audit/logs` | 审计日志列表（分页） |
| GET | `/api/v1/audit/logs/{log_id}` | 审计日志详情 |

**MCP 工具（rag-service，只读）**：

| 工具 | 说明 |
| --- | --- |
| `retrieve_docs` | 检索与查询最相关的知识片段（支持 top_k / 相似度阈值 / MMR / 元数据过滤） |
| `rag_query` | 基于知识库内容生成完整回答（检索 → 增强 → 生成），返回答案与引用片段 |

### 🔐 权限与访问控制

- **agent-service**：工具中心遵循"只读工具可直接调用、写操作由人工执行"原则；任务路由支持 explicit / llm / hybrid 三种模式；生产环境（`APP_ENV=production`）强制校验 —— 禁止 DEBUG、CORS 白名单不能为 `*`、checkpoint 必须为 redis；
- **rag-service**：内置 slowapi 限流（`RATE_LIMIT_ENABLED` / 每分钟 / 每小时配额）；所有写操作（文档上传 / 删除、同步触发）均写入审计日志，操作人固定为 `internal`；审计接口只读。

## 💾 存储配置说明

| 存储 | 用途 | 配置参数 | 备注 |
| --- | --- | --- | --- |
| MySQL 8.0 | rag-service：审计日志 / 同步任务状态；agent-service：Agent 任务 / 事件 | `DATABASE_URL` / `QINGCHUAN_AGENT_DATABASE_*` | 生产必需；本地可 SQLite 或无库运行（agent-service 默认关闭） |
| Chroma 向量库 | 稠密向量索引（文档向量） | `VECTOR_STORE_PERSIST_DIR=./data/chroma`、`VECTOR_STORE_COLLECTION_NAME`、`VECTOR_STORE_DISTANCE` | 持久化于 `apps/rag-service/data/chroma` |
| BM25 索引 | 稀疏检索索引（关键词匹配） | `./data/bm25/documents.json` | 随文档索引自动构建 |
| 文档存储 | 上传的源文档 | `./data/documents` | DocumentRepository 存储路径 |
| 日志文件 | loguru 文件轮转 | `LOG_FILE_PATH` / `QINGCHUAN_AGENT_LOGGING_FILE_PATH` | 轮转 1 天 / 保留 7 天 / zip 压缩 |

数据结构定义（ORM 实体）：

- **rag-service**：`audit_logs`（操作人 / 操作 / 对象 / 结果 / 时间戳）、`sync_tasks`（类型 / 状态 / 批次 / 成功失败数）；
- **agent-service**：`agent_tasks`（task_type / payload / status / result / error / 线程 ID）、`agent_events`（事件类型 / payload / 关联任务）。

## 📄 许可证

[MIT 许可证](LICENSE) © 2026 ChainEngine

## 📚 参考资料

- Python: <https://www.python.org/>
- uv: <https://docs.astral.sh/uv/>
- FastAPI: <https://fastapi.tiangolo.com/>
- Uvicorn: <https://www.uvicorn.org/>
- LangGraph: <https://langchain-ai.github.io/langgraph/>
- LangChain: <https://python.langchain.com/>
- MCP（Model Context Protocol）: <https://modelcontextprotocol.io/>
- ChromaDB: <https://docs.trychroma.com/>
- sentence-transformers: <https://www.sbert.net/>
- rank-bm25: <https://github.com/dorianbrown/rank_bm25>
- SQLAlchemy: <https://www.sqlalchemy.org/>
- PyMySQL: <https://pymysql.readthedocs.io/>
- APScheduler: <https://apscheduler.readthedocs.io/>
- pydantic: <https://docs.pydantic.dev/>
- loguru: <https://loguru.readthedocs.io/>
- Docker: <https://docs.docker.com/>

## 📮 联系方式

- **作者**：John Young（夜雨诗来）
- **邮箱**：john.young@foxmail.com
- **Gitee**：<https://gitee.com/yeyushilai>
- **GitHub**：<https://github.com/yeyushilai>
- **项目地址**：<https://github.com/chain-engine/x-QingChuan>
