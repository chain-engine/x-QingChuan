# 晴川 QingChuan（x-QingChuan）

人社 API 离线索引 + RAG 检索 + Agent 智能问答平台。
让政务领域知识可检索、可问答、可编排——以人社数据为知识底座，HTTP 与 MCP 双协议开放，LangGraph 多 Agent 智能调度。

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
![月提交数](https://img.shields.io/github/commit-activity/m/chain-engine/x-QingChuan?label=Commits)

## 💡 项目介绍

晴川是面向人社业务场景的**多 Agent 编排 + 知识库赋能平台**，采用 uv monorepo 结构，由两个可独立部署的服务与两个共享包组成：

- **rag-service（qingchuan-rag）**：人社数据离线索引 + RAG（检索增强生成）一体化服务，对外提供 **HTTP + MCP 双协议**；离线索引管道（CLI + APScheduler 定时任务）随服务发布；
- **agent-service（qingchuan-agent）**：**LangGraph 多 Agent 编排运行时** + HTTP 服务；顶层调度图 `route → 子图 → aggregate`，新 Agent 在 `agents/` 登记即扩展；经 MCP 工具调用 rag-service，不持有索引写权限；
- **packages/domain（qingchuan-domain）**：实体 / Schema / 检索协议 / 端口单一事实来源，两服务直接引用；
- **packages/common（qingchuan-common）**：跨服务通用件（MCP 客户端封装 / 鉴权 / 审计 / 观测，占位）。

**当前状态**：RAG 检索链路可端到端运行（人社同步支持 mock 数据联调）；Agent 编排骨架已交付（业务 Agent 注册即扩展），任务 / 事件持久化默认关闭可无库启动。

## 🚀 快速开始

### 🖥️ 1. 环境要求

- **Windows / Linux / macOS** 均可，需 Python 3.12+（`requires-python = ">=3.12,<3.14"`）；
- **uv** 包管理器（workspace 依赖同步必需）：<https://docs.astral.sh/uv/>；
- **Docker / Docker Compose**（容器部署时需要，本地开发可选）；
- **MySQL 8.0**（生产推荐；本地可无库启动或 SQLite，agent-service 持久化默认关闭）。

### 📥 2. 项目代码克隆

```bash
git clone https://github.com/chain-engine/x-QingChuan.git
cd x-QingChuan
```

### 📦 3. 依赖同步安装

```bash
uv lock                 # 首次：生成锁文件
uv sync --all-packages  # 安装 workspace 全部成员（apps/* 与 packages/*）
```

### ⚙️ 4. 环境配置

复制示例文件并按需修改（核心参数见下表）：

```bash
# rag-service：支持 .env 与 config.yaml 两种配置方式
cp apps/rag-service/.env.example apps/rag-service/.env
# 或
cp apps/rag-service/config.yaml.example apps/rag-service/config.yaml

# agent-service：配置位于项目根目录 .env（前缀 QINGCHUAN_AGENT_）
```

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `DATABASE_URL` | `mysql+pymysql://yeyushilai:123456@localhost:3306/qingchuan` | rag-service 业务库（审计 / 同步任务），本地可 SQLite |
| `SYNC_ENABLED` / `SYNC_CRON` | `false` / `0 3 * * *` | 人社数据周期同步开关与 cron 表达式 |
| `HRSS_API_URL` / `HRSS_API_TOKEN` | 空 | 人社数据源地址与 Bearer Token（生产必填） |
| `HRSS_MOCK` | `true` | mock 模式：无真实 API 时用本地示例数据端到端联调 |
| `EMBEDDING_MODEL` | `BAAI/bge-m3` | 嵌入模型（本地离线推理） |
| `VECTOR_STORE_PERSIST_DIR` | `./data/chroma` | Chroma 向量库持久化目录 |
| `GENERATION_PROVIDER` / `GENERATION_MODEL` | `mimo` / `mimo-v2.6-pro` | 生成模型，支持 DeepSeek / 豆包 / 阿里百炼 / 小米 MiMo |
| `QINGCHUAN_AGENT_DATABASE_ENABLED` | `false` | agent-service 任务 / 事件持久化开关（开启后首次启动自动建表） |
| `QINGCHUAN_AGENT_RAG_HTTP_BASE_URL` | `http://rag-service:8010` | agent 侧 rag 客户端地址（本地改为 `http://127.0.0.1:8010`） |

### 🚀 5. 服务启动

**本地开发热重载**：

```bash
# rag-service：HTTP 服务（默认 0.0.0.0:8010，MCP 随服务挂载在 /mcp）
uv run --package qingchuan-rag qingchuan-rag-api
# 或
uv run --package qingchuan-rag uvicorn qingchuan_rag.main:app --reload --host 0.0.0.0 --port 8010

# agent-service：HTTP 服务（默认 127.0.0.1:8020）
uv run --package qingchuan-agent qingchuan-agent-api
# 或
uv run --package qingchuan-agent uvicorn qingchuan_agent.main:app --reload --host 127.0.0.1 --port 8020

# agent-service：编排 demo（骨架占位，验证注册表 / 路由 / 运行时链路）
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
uv run pytest                  # 单元测试（rag-service 目录下）
pre-commit run --all-files     # pre-commit 钩子（ruff --fix + ruff-format）
uv audit                       # 依赖漏洞扫描（uv 0.5+ 内置）
```

### 💬 7. 使用方法示例

**RAG 检索问答（rag-service HTTP）**：

```bash
curl -X POST http://127.0.0.1:8010/api/v1/rag/query \
  -H "Content-Type: application/json" \
  -d '{"query": "社保缴费基数如何确定？"}'
```

**触发人社数据同步**：

```bash
uv run --package qingchuan-rag qingchuan-pipeline sync --full
# 或 HTTP 触发
curl -X POST http://127.0.0.1:8010/api/v1/sync/trigger \
  -H "Content-Type: application/json" \
  -d '{"full": true}'
```

**MCP 检索调用**：MCP 客户端接入示例见 `apps/rag-service/scripts/qingchuan_mcp_client.py`；HTTP 客户端示例见 `apps/rag-service/scripts/qingchuan_http_client.py`。

**提交 Agent 任务（agent-service）**：

```bash
curl -X POST http://127.0.0.1:8020/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{"task_type": "agent_a", "payload": {"query": "..."}}'
```

### ❓ 8. 常见问题排查

| 现象 | 解决方案 |
| --- | --- |
| 端口被占用 | 修改 `SERVER_PORT`（rag-service）或 `QINGCHUAN_AGENT_SERVER_PORT`（agent-service） |
| uv 安装依赖失败 / 超时 | 检查网络；rag-service 已内置阿里云 PyPI 镜像，可在根 `pyproject.toml` 追加 `[tool.uv.index]` |
| torch 在 Windows 报 `shm.dll` 缺失 | 保持 `torch==2.12.0` 锁定版本，勿升级至 2.14.x |
| 数据库连接失败 | 确认 MySQL 已启动且库已创建（`utf8mb4`）；agent-service 可先关闭 `QINGCHUAN_AGENT_DATABASE_ENABLED` 无库启动 |
| 人社同步 401 / 超时 | 联调期保持 `HRSS_MOCK=true`；对接真实 API 需配置 `HRSS_API_URL` / `HRSS_API_TOKEN` 并关闭 mock |
| 配置加载异常导致启动失败 | 配置非法会直接阻断启动（validate），按报错字段修正；生产环境禁止 DEBUG / `*` CORS / memory checkpoint |

## 📁 项目结构

```text
x-QingChuan/
├── apps/
│   ├── agent-service/                  # Agent 编排运行时 + HTTP 服务（可独立部署，:8020）
│   │   ├── src/qingchuan_agent/
│   │   │   ├── main.py                 # FastAPI 入口（lifespan / 中间件 / 异常处理 / 路由挂载）
│   │   │   ├── cli.py                  # CLI：qingchuan-agent（编排 demo）/ qingchuan-agent-api
│   │   │   ├── api/                    # 接口层：/api/v1（health / version / agents / tasks / events）
│   │   │   ├── services/               # 业务逻辑层（AgentTaskService 任务全生命周期）
│   │   │   ├── repositories/           # 数据访问层（任务 / 事件仓储）
│   │   │   ├── models/                 # ORM 实体（AgentTask / AgentEvent）
│   │   │   ├── schemas/                # 请求 / 响应 Schema（ApiResponse / Page 统一包装）
│   │   │   ├── agents/                 # 编排层：orchestrator / registry / runtime / base / state / routing / tools
│   │   │   ├── infras/                 # 基础设施（MySQL Provider / LLM Provider / 事件总线）
│   │   │   ├── core/                   # 核心基础设施（config / logger / exceptions / middleware）
│   │   │   ├── constants/              # 常量与枚举包（base 枚举基类族 / constants / enums）
│   │   │   ├── templates/              # 提示词模板（LLM 路由提示词）
│   │   │   └── utils/                  # 通用工具（IP 提取 / 脱敏）
│   │   ├── Dockerfile
│   │   └── pyproject.toml              # qingchuan-agent
│   └── rag-service/                    # RAG 服务：HTTP + MCP 双协议（可独立部署，:8010）
│       ├── src/qingchuan_rag/
│       │   ├── main.py                 # FastAPI 入口（挂载 HTTP 路由 + /mcp Streamable HTTP）
│       │   ├── cli.py                  # CLI：qingchuan-rag-api / qingchuan-pipeline
│       │   ├── http_server/            # HTTP 出口（v1：health / rag / document / sync / audit_log）
│       │   ├── mcp_server/             # MCP 出口（server / tools / prompts / resources）
│       │   ├── sync/                   # 人社数据同步（scheduler 调度器 / sync_service 同步服务）
│       │   ├── services/               # 业务服务（document / rag / sync / retrieval_adapter / audit）
│       │   ├── repositories/           # 数据仓储（document / vector / bm25 / sync_task / audit_log）
│       │   ├── rag/                    # RAG 流水线（retrieval / augmentation / generation / pipeline）
│       │   ├── retrieval/              # 混合检索（向量 + BM25）
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
│   ├── common/                         # 跨服务通用件（MCP 客户端 / 鉴权 / 审计 / 观测，占位）
│   │   └── src/qingchuan_common/
│   └── domain/                         # 共享领域包（实体 / Schema / 检索协议 / 端口，单一事实来源）
│       └── src/qingchuan_domain/
├── docker-compose.yml                  # 一键编排 rag-service + agent-service
├── pyproject.toml                      # uv workspace 根（members: apps/*, packages/*）
├── .env                                # 环境配置（不入库）
├── .pre-commit-config.yaml             # pre-commit 钩子（ruff）
├── LICENSE                             # MIT License
├── README.md / README.en.md            # 中英文双语文档
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
        B2["业务服务层（services/）"]
        B3["Agent 编排层（agents/）"]
        B4["数据访问层（repositories/）"]
    end

    subgraph RAG["rag-service（qingchuan-rag，:8010）"]
        C1["HTTP 出口（/api/v1）"]
        C2["MCP 出口（/mcp）"]
        C3["业务服务层（services/）"]
        C4["数据仓储层（repositories/）"]
    end

    subgraph INFRA["基础设施"]
        D1[("MySQL 业务库")]
        D2[("Chroma 向量库")]
        D3[("BM25 稀疏索引")]
        D4["LLM Provider（OpenAI 兼容）"]
        D5["人社数据源（HRSS API）"]
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

**Agent 编排流程（route → 子图 → aggregate）**：

```mermaid
flowchart LR
    START["提交任务"] --> ROUTE["route 节点<br/>（注册表路由 explicit / llm / hybrid）"]
    ROUTE -->|"已注册 Agent"| SUB["子图节点<br/>（业务 Agent：MCP 检索 → LLM 生成）"]
    SUB --> AGG["aggregate<br/>（聚合事件与结果）"]
    AGG --> END["返回任务结果"]
    ROUTE -->|"未注册 / 路由失败"| FAIL["任务失败（回写 error）"]
    FAIL --> END
    SUB -. "interrupt 人工接管" .-> WAIT["等待人工<br/>（resume 断点续跑）"]
    WAIT --> SUB
```

**RAG 离线同步 + 在线问答**：

```mermaid
flowchart LR
    subgraph OFFLINE["离线索引管道"]
        S1["人社数据同步<br/>（CLI / APScheduler / HTTP 触发）"] --> S2["文本切分"]
        S2 --> S3["Embedding（bge-m3）"]
        S3 --> S4["向量入库 Chroma + BM25 索引"]
    end

    subgraph ONLINE["在线问答"]
        Q1["用户提问"] --> Q2["混合检索<br/>（向量 + BM25 + MMR）"]
        Q2 --> Q3["重排增强"]
        Q3 --> Q4["LLM 生成（带来源）"]
        Q4 --> Q5["返回答案"]
    end

    S4 -.-> Q2
```

### 🔩 关键技术组件

| 模块 | 组件 | 说明 |
| --- | --- | --- |
| Web 框架 | FastAPI + Uvicorn | 双服务 HTTP 出口，统一响应包装与异常处理 |
| Agent 编排 | LangGraph | 顶层调度图 + 业务子图嵌套，interrupt / resume 断点续跑 |
| 注册 / 路由 | AgentRegistry | task_type → AgentSpec 映射表路由，惰性编译缓存 |
| LLM 接入 | LangChain（OpenAI 兼容） | DeepSeek / 豆包 / 阿里百炼 / 小米 MiMo |
| MCP | mcp 2.3+ | rag-service Streamable HTTP（/mcp）；agent 经 MCP 客户端调用 |
| 向量检索 | ChromaDB + sentence-transformers（BAAI/bge-m3） | 稠密索引，持久化 `data/chroma` |
| 稀疏检索 | rank-bm25 | BM25 索引，与向量混合检索 |
| 业务库 | SQLAlchemy 2 + PyMySQL（MySQL 8） | 审计日志 / 同步任务 / Agent 任务事件 |
| 周期调度 | APScheduler | 人社数据同步 cron（默认每天 03:00） |
| 配置 | pydantic-settings / pydantic + PyYAML | 分段前缀配置，非法配置阻断启动 |
| 日志 | loguru | 控制台彩色 / 文件轮转（1 天 / 保留 7 天） |
| 工程化 | uv + ruff + pre-commit + pytest | workspace 依赖、静态检查、测试 |
| 部署 | Docker Compose | rag-service + agent-service 一键编排 |

## 🛠️ 技术栈

| 分类 | 选型 |
| --- | --- |
| 开发语言 | Python 3.12+ |
| Web 框架 | FastAPI 0.115+ / Uvicorn 0.30+ |
| Agent 编排 | LangGraph 0.2+（顶层编排图 + 业务子图，interrupt / resume） |
| LLM 接入 | LangChain（langchain-core 0.3+ / langchain-openai 0.2+，OpenAI 兼容协议） |
| MCP | mcp 2.3+（Streamable HTTP） |
| 向量数据库 | ChromaDB 0.4+ |
| 嵌入模型 | sentence-transformers（BAAI/bge-m3） |
| 稀疏检索 | rank-bm25 0.2+ |
| 业务数据库 | MySQL 8.0（SQLAlchemy 2 + PyMySQL；本地可 SQLite） |
| 周期调度 | APScheduler 3.10+ |
| 配置管理 | pydantic-settings 2.5+ / pydantic 2.9+ / PyYAML |
| 日志 | loguru 0.7+ |
| 包管理 | uv（workspace：apps/* + packages/*，uv.lock） |
| 工程化 | ruff + pre-commit + pytest（pytest-asyncio / pytest-cov） |
| 部署运维 | Docker / Docker Compose |

## 📡 API 文档说明

两个服务均启用 **Swagger 交互式文档 / ReDoc 只读文档 / OpenAPI JSON**：

| 服务 | Swagger | ReDoc | OpenAPI JSON | MCP 端点 |
| --- | --- | --- | --- | --- |
| rag-service（:8010） | <http://127.0.0.1:8010/docs> | <http://127.0.0.1:8010/redoc> | <http://127.0.0.1:8010/openapi.json> | <http://127.0.0.1:8010/mcp>（Streamable HTTP） |
| agent-service（:8020） | <http://127.0.0.1:8020/docs> | <http://127.0.0.1:8020/redoc> | <http://127.0.0.1:8020/openapi.json> | —（经 MCP 客户端调用 rag-service） |

### 核心 API 清单

**agent-service（/api/v1，共 9 个）**：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/health` | 健康检查（含 DB / Agent 运行时状态） |
| GET | `/api/v1/version` | 版本信息 |
| GET | `/api/v1/agents/specs` | 已注册 Agent 规格 |
| POST | `/api/v1/tasks` | 提交 Agent 任务（task_type 显式路由 / 留空走 LLM 动态路由） |
| GET | `/api/v1/tasks` | 任务列表（分页） |
| GET | `/api/v1/tasks/{id}` | 任务详情 |
| POST | `/api/v1/tasks/{id}/resume` | 人工接管：恢复被 interrupt 的任务 |
| GET | `/api/v1/events` | 协作事件列表（分页） |
| GET | `/api/v1/events/{id}` | 事件详情 |

**rag-service（/api/v1，核心子集）**：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/health` / `/version` / `/status` | 健康 / 版本 / 系统状态 |
| POST | `/api/v1/rag/query` | RAG 问答（检索 + 生成） |
| POST | `/api/v1/rag/retrieve` | 文本检索（不生成，返回片段与来源） |
| POST | `/api/v1/rag/embed` | 文本向量化 |
| GET | `/api/v1/rag/stats` | RAG 系统统计 |
| POST | `/api/v1/documents/upload` | 文档上传并自动索引 |
| GET | `/api/v1/documents` | 文档列表（分页） |
| GET | `/api/v1/documents/{document_id}` | 文档详情 |
| DELETE | `/api/v1/documents/{document_id}` | 删除文档及其向量 |
| GET | `/api/v1/documents/{document_id}/status` | 文档处理状态 |
| POST | `/api/v1/sync/trigger` | 触发人社数据同步（默认增量，`full=true` 全量） |
| GET | `/api/v1/sync/status` | 最近同步状态 |
| GET | `/api/v1/sync/status/{task_id}` | 同步任务状态 |
| GET | `/api/v1/logs` | 审计日志列表（分页） |
| GET | `/api/v1/logs/{log_id}` | 审计日志详情 |

**MCP 工具（rag-service，只读）**：

| 工具 | 说明 |
| --- | --- |
| `retrieve_docs` | 检索与查询最相关的知识片段（支持 top_k / 相似度阈值 / MMR / 元数据过滤） |

### 权限控制说明

- **agent-service**：工具中心遵循「只读可直调、写操作由人工执行」原则；任务路由支持 explicit / llm / hybrid 三种模式；生产环境（`APP_ENV=production`）强制校验——禁止 DEBUG、CORS 白名单不可为 `*`、checkpoint 必须为 redis；
- **rag-service**：内置 slowapi 限流（`RATE_LIMIT_ENABLED` / 每分钟 / 每小时配额）；所有写操作（文档上传 / 删除、同步触发）写入审计日志，操作人固定 `internal`，审计日志接口只读。

## 💾 存储配置说明

| 存储 | 用途 | 配置参数 | 说明 |
| --- | --- | --- | --- |
| MySQL 8.0 | rag-service：审计日志 / 同步任务状态；agent-service：Agent 任务 / 事件 | `DATABASE_URL` / `QINGCHUAN_AGENT_DATABASE_*` | 生产必配；本地可 SQLite 或无库启动（agent-service 默认关闭） |
| Chroma 向量库 | 稠密向量索引（文档 Embedding） | `VECTOR_STORE_PERSIST_DIR=./data/chroma`、`VECTOR_STORE_COLLECTION_NAME`、`VECTOR_STORE_DISTANCE` | 持久化目录 `apps/rag-service/data/chroma` |
| BM25 索引 | 稀疏检索索引（关键词匹配） | `./data/bm25/documents.json` | 随文档索引自动构建 |
| 文档存储 | 上传的原始文档 | `./data/documents` | DocumentRepository 存储路径 |
| 日志文件 | loguru 文件轮转 | `LOG_FILE_PATH` / `QINGCHUAN_AGENT_LOGGING_FILE_PATH` | 轮转 1 天 / 保留 7 天 / zip 压缩 |

数据结构定义（ORM 实体）：

- **rag-service**：`audit_logs`（审计日志：操作人 / 动作 / 目标 / 结果 / 时间）、`sync_tasks`（同步任务：类型 / 状态 / 批次 / 成功失败数）；
- **agent-service**：`agent_tasks`（任务：task_type / payload / status / result / error / 线程 ID）、`agent_events`（协作事件：事件类型 / 载荷 / 关联任务）。

## 📄 许可证

[MIT License](LICENSE) © 2026 ChainEngine

## 📚 参考资料

- Python：<https://www.python.org/>
- uv：<https://docs.astral.sh/uv/>
- FastAPI：<https://fastapi.tiangolo.com/>
- Uvicorn：<https://www.uvicorn.org/>
- LangGraph：<https://langchain-ai.github.io/langgraph/>
- LangChain：<https://python.langchain.com/>
- MCP（Model Context Protocol）：<https://modelcontextprotocol.io/>
- ChromaDB：<https://docs.trychroma.com/>
- sentence-transformers：<https://www.sbert.net/>
- rank-bm25：<https://github.com/dorianbrown/rank_bm25>
- SQLAlchemy：<https://www.sqlalchemy.org/>
- PyMySQL：<https://pymysql.readthedocs.io/>
- APScheduler：<https://apscheduler.readthedocs.io/>
- pydantic：<https://docs.pydantic.dev/>
- loguru：<https://loguru.readthedocs.io/>
- Docker：<https://docs.docker.com/>

## 📮 联系方式

- **作者**：John Young（夜雨诗来）
- **邮箱**：john.young@foxmail.com
- **Gitee**：<https://gitee.com/yeyushilai>
- **GitHub**：<https://github.com/yeyushilai>
- **项目地址**：<https://github.com/chain-engine/x-QingChuan>
