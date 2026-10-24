# 晴川（QingChuan）

人社（HRSS）数据离线索引 + RAG（检索增强生成） + 人机交互的多 Agent 编排平台（当前第一期聚焦智能问答）。
让政务领域知识可检索、可问答、可编排 —— 基于人社数据，通过 HTTP + MCP 双协议服务对外暴露，由 LangGraph 多智能体编排调度。

[English](README.en.md) | 中文

![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python\&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi\&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2%2B-1C3C3C)
![LangChain](https://img.shields.io/badge/LangChain-0.3%2B-1C3C3C?logo=langchain\&logoColor=white)
![MCP](https://img.shields.io/badge/MCP-2.3%2B-24292F)
![ChromaDB](https://img.shields.io/badge/ChromaDB-0.4%2B-F97316)
![BM25](https://img.shields.io/badge/BM25-Incremental%20Index-2C3E50)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0%2B-D71F00?logo=sqlalchemy\&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-8.0-4479A1?logo=mysql\&logoColor=white)
![APScheduler](https://img.shields.io/badge/APScheduler-3.10%2B-2C3E50)
![Docker](https://img.shields.io/badge/Docker-24.0%2B-2496ED?logo=docker\&logoColor=white)
![uv](https://img.shields.io/badge/uv-0.5%2B-6E40C9)

![Stars](https://img.shields.io/github/stars/chain-engine/x-QingChuan?label=Stars)
![Forks](https://img.shields.io/github/forks/chain-engine/x-QingChuan?label=Forks)
![License](https://img.shields.io/github/license/chain-engine/x-QingChuan?label=License)
![Commits](https://img.shields.io/github/commit-activity/m/chain-engine/x-QingChuan?label=Commits)

## 💡 项目介绍

晴川是一个面向**人社（HRSS）业务场景**的 **数据离线索引 + RAG 检索增强生成 + 人机交互多 Agent 编排平台**（当前第一期聚焦智能问答）。工程采用 uv monorepo 结构，包含两个可独立部署的服务与两个共享包：

- **rag-service（qingchuan-rag）**：人社（HRSS）数据离线索引 + RAG（检索增强生成）一体化服务平台，对外暴露 **HTTP + MCP 双协议**；离线索引流水线（CLI + APScheduler 周期任务）随服务内置；
- **agent-service（qingchuan-agent）**：**人机交互的多智能体编排平台**（LangGraph 编排运行时 + HTTP 服务）；顶层编排图执行 `route → subagent → aggregate`，新 Agent 在 `agents/` 目录注册即可扩展；经 MCP 工具调用 rag-service，不持有索引写权限；
- **packages/domain（qingchuan-domain）**：实体 / Schema / 检索协议 / 端口的唯一事实来源，两个服务直接引用；
- **packages/common（qingchuan-common）**：跨服务共享组件（MCP 客户端封装 / 认证 / 审计 / 可观测性，占位）。

**当前状态**：第一期聚焦智能问答——RAG 检索问答链路已端到端跑通（人社同步支持 mock 数据联调，问答（客服）Agent 链路已闭环）；BM25 采用自研增量倒排索引，文本切分支持 recursive / semantic 等策略；Agent 编排骨架已交付（新业务 Agent 注册即可扩展），任务 / 事件持久化默认关闭，无数据库也可启动服务。

## 🚀 快速开始

### 🖥️ rag-service（人社数据离线索引 + RAG 一体化服务）

```bash
cd apps/rag-service
uv run qingchuan-rag-api
```

访问 <http://127.0.0.1:8010>（MCP 挂载于 /mcp），详见 [rag-service/README.md](apps/rag-service/README.md)。

### 🤖 agent-service（人机交互多智能体编排平台）

```bash
cd apps/agent-service
uv run qingchuan-agent-api
```

访问 <http://127.0.0.1:8020>，详见 [agent-service/README.md](apps/agent-service/README.md)。

> **Docker 部署**：`docker compose up -d --build` 一次性编排 MySQL、Redis、rag-service、agent-service（内部网络互通；向量库默认 Chroma 本地持久化，零外部依赖）；宿主调试端口：MySQL 13306 / Redis 16379 / rag 8010 / agent 8020。需要 Milvus 时追加 `docker compose --profile milvus up -d`（etcd + MinIO + Milvus standalone，见 [DEPLOY.md](DEPLOY.md)）。

## 📁 项目结构

```text
x-QingChuan/
├── apps/
│   ├── agent-service/                  # 人机交互多智能体编排平台（独立部署，:8020）
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
│   └── rag-service/                    # 人社数据离线索引 + RAG 一体化服务平台（独立部署，:8010）
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
├── docker-compose.yml                  # 一键部署 mysql + redis + rag-service + agent-service（向量库默认 Chroma；Milvus 三件套走 --profile milvus 可选）
├── pyproject.toml                      # uv 工作区根（members：apps/*、packages/*）
├── .env                                # 环境配置（不入库）
├── .pre-commit-config.yaml             # pre-commit 钩子（ruff）
├── LICENSE                             # MIT 许可证
├── me/                                 # 系统架构图（architecture.svg 中文 / architecture.en.svg 英文）
├── README.md / README.en.md            # 中英双语文档
└── uv.lock                             # 依赖锁文件
```

## 🏗️ 系统架构

### 🧱 系统分层架构

![系统分层架构](./me/architecture.svg)

> 分层架构图（中文版）：客户端 → 服务层（agent-service / rag-service）→ 基础设施（MySQL / Redis / Milvus / BM25 / LLM / 人社源）

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

| 模块       | 组件                                                                                               | 说明                                                                     |
| -------- | ------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------- |
| Web 框架   | FastAPI + Uvicorn                                                                                | 两个服务的 HTTP 网关，统一响应包装与异常处理                                              |
| Agent 编排 | LangGraph                                                                                        | 顶层编排图 + 嵌套业务子图，interrupt / resume                                      |
| 注册 / 路由  | AgentRegistry                                                                                    | task\_type → AgentSpec 映射表路由，惰性编译缓存                                    |
| LLM 接入   | LangChain（OpenAI 兼容）                                                                             | DeepSeek / 豆包 / 阿里云百炼 / 小米 MiMo                                        |
| MCP      | mcp 2.3+                                                                                         | rag-service Streamable HTTP（/mcp）；agent 经 MCP 客户端调用                    |
| 向量检索     | ChromaDB（默认，本地持久化，零外部依赖）/ Milvus（可选：extras + compose --profile milvus 启用 etcd+MinIO+standalone）+ sentence-transformers（BAAI/bge-m3） | 稠密索引；默认持久化于 `data/chroma`，切换 Milvus 经 `VECTOR_STORE_TYPE=milvus` |
| 稀疏检索     | BM25IndexStore（自研增量倒排）                                                                           | 倒排表 + Okapi BM25 打分，增删 O(词数) 增量维护，与向量检索混合；rank-bm25 仅一致性对比与备用路径        |
| 业务库      | SQLAlchemy 2 + PyMySQL（MySQL 8）                                                                  | 审计日志 / 同步任务 / Agent 任务与事件                                              |
| 缓存 / 状态  | Redis 7                                                                                          | agent checkpoint（生产强制 redis）+ 事件总线                                     |
| 周期调度     | APScheduler                                                                                      | 人社同步 cron（默认每日 03:00）                                                  |
| 配置       | pydantic-settings / pydantic + PyYAML                                                            | 分段带前缀配置；非法配置阻断启动                                                       |
| 日志       | loguru                                                                                           | 彩色控制台 / 文件轮转（1 天 / 保留 7 天）                                             |
| 工程化      | uv + ruff + pre-commit + pytest                                                                  | 工作区依赖、静态检查、测试                                                          |
| 部署       | Docker Compose                                                                                   | 一键独立部署 MySQL + Redis + 双服务（内部网络，不依赖宿主机）；Milvus 可选（--profile milvus 启用 etcd+MinIO+standalone） |

## 🛠️ 技术栈

| 分类       | 选型                                                                           |
| -------- | ---------------------------------------------------------------------------- |
| 开发语言     | Python 3.12+                                                                 |
| Web 框架   | FastAPI 0.115+ / Uvicorn 0.30+                                               |
| Agent 编排 | LangGraph 0.2+（顶层图 + 业务子图，interrupt / resume）                                |
| LLM 接入   | LangChain（langchain-core 0.3+ / langchain-openai 0.2+，OpenAI 兼容协议）           |
| MCP      | mcp 2.3+（Streamable HTTP）                                                    |
| 向量数据库    | ChromaDB 0.4+（可选 Milvus 2.x / milvus-lite）                                   |
| 向量嵌入     | sentence-transformers 5.7+（BAAI/bge-m3）                                      |
| 稀疏检索     | 自研 BM25 增量倒排（rank-bm25 0.2+ 备用 / 对比）                                         |
| 文本切分     | langchain-text-splitters 1.1+ / llama-index-core 0.14+ / 自研 SemanticSplitter |
| 业务数据库    | MySQL 8.0（SQLAlchemy 2 + PyMySQL；本地可 SQLite）                                 |
| 周期调度     | APScheduler 3.10+                                                            |
| 配置管理     | pydantic-settings 2.5+ / pydantic 2.9+ / PyYAML                              |
| 日志       | loguru 0.7+                                                                  |
| 包管理      | uv（工作区：apps/\* + packages/\*，uv.lock）                                        |
| 工程化      | ruff + pre-commit + pytest（pytest-asyncio / pytest-cov）                      |
| 部署       | Docker / Docker Compose                                                      |

## 📡 API 文档说明

两个服务均开启 **Swagger 交互式文档 / ReDoc 只读文档 / OpenAPI JSON**：

| 服务                   | Swagger                      | ReDoc                         | OpenAPI JSON                         |
| -------------------- | ---------------------------- | ----------------------------- | ------------------------------------ |
| rag-service（:8010）   | <http://127.0.0.1:8010/docs> | <http://127.0.0.1:8010/redoc> | <http://127.0.0.1:8010/openapi.json> |
| agent-service（:8020） | <http://127.0.0.1:8020/docs> | <http://127.0.0.1:8020/redoc> | <http://127.0.0.1:8020/openapi.json> |

### 📋 核心 API 接口清单

**rag-service（/api/v1）**：

| 方法           | 路径                                                      | 说明                                                         |
| ------------ | ------------------------------------------------------- | ---------------------------------------------------------- |
| GET          | `/api/v1/health` / `/api/v1/version` / `/api/v1/status` | 健康检查 / 版本 / 运行状态                                           |
| POST         | `/api/v1/rag/query`                                     | RAG 问答（检索 + 生成，支持 top\_k / 阈值 / MMR / 元数据过滤 / 指定 provider） |
| POST         | `/api/v1/rag/retrieve` / `/api/v1/rag/embed`            | 仅检索不生成 / 文本向量化                                             |
| POST         | `/api/v1/documents/upload`                              | 上传文档并自动索引（UTF-8 / GBK 编码）                                  |
| GET          | `/api/v1/documents`                                     | 文档列表（分页，可按状态 / 类型过滤）                                       |
| GET / DELETE | `/api/v1/documents/{document_id}`                       | 文档详情 / 删除文档及其向量                                            |
| POST         | `/api/v1/sync/trigger`                                  | 触发人社同步（`full=true` 全量，`force=true` 强制重跑）                   |
| GET          | `/api/v1/sync/status`                                   | 最近一次同步状态                                                   |
| GET          | `/api/v1/audit/logs`                                    | 审计日志列表（按实体 / 操作 / 操作者 / 时间范围 / 关键字分页）                      |

MCP 端点：`/mcp`（Streamable HTTP），工具 `retrieve_docs` / `rag_query`（只读）。

**agent-service（/api/v1）**：

| 方法   | 路径                                             | 说明                                            |
| ---- | ---------------------------------------------- | --------------------------------------------- |
| GET  | `/api/v1/health` / `/api/v1/version`           | 健康检查（含 DB / Agent 运行时状态）/ 版本信息                |
| GET  | `/api/v1/agents/specs`                         | 已注册 Agent 规格列表                                |
| POST | `/api/v1/tasks`                                | 提交 Agent 任务（显式 task\_type 直接路由；留空 → LLM 动态路由） |
| GET  | `/api/v1/tasks`                                | 任务列表（分页，可按状态 / 类型过滤）                          |
| GET  | `/api/v1/tasks/{task_id}`                      | 任务详情                                          |
| POST | `/api/v1/tasks/{task_id}/resume`               | 人工接管：恢复被中断的任务                                 |
| GET  | `/api/v1/events` / `/api/v1/events/{event_id}` | 协作事件列表 / 详情                                   |

### 🔐 权限与访问控制

- 内部服务不设应用鉴权：rag-service 所有写操作（文档上传 / 删除、同步触发）经 AuditService 写入审计日志（操作人固定 `internal`）；agent-service 只读工具（MCP 检索）可直接调用，写操作由人工执行，不持有 rag-service 索引写权限；
- rag-service 内置 slowapi 限流（`RATE_LIMIT_ENABLED`）；两个服务生产环境均禁止 DEBUG 与 CORS `*`（agent 侧 `APP_ENV=production` 强制校验），非法配置直接阻断启动。

## 💾 存储配置说明

| 存储         | 用途                                         | 配置参数                                                                                                                                        | 备注                                                                                                                                                                                                             |
| ---------- | ------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| MySQL 8.0  | 审计日志 / 同步任务（rag）；Agent 任务 / 事件（agent，默认关闭） | rag：`DATABASE_URL`；agent：`QINGCHUAN_AGENT_DATABASE_*`                                                                                       | 本地可 SQLite（`sqlite:///./data/qingchuan.db`）；库需提前创建（`utf8mb4`）                                                                                                                                                  |
| Chroma 向量库 | 稠密向量索引（文档向量）                               | `VECTOR_STORE_TYPE=chroma`、`VECTOR_STORE_PERSIST_DIR=./data/chroma`、`VECTOR_STORE_COLLECTION_NAME=documents`、`VECTOR_STORE_DISTANCE=cosine` | **默认选型**：本地持久化，零外部依赖（单机 / 云主机直接可用）                                                                                                                                                                             |
| Milvus 向量库 | 稠密向量索引（Milvus 形态）                          | 需安装 extras：`uv sync --extra milvus`；`VECTOR_STORE_TYPE=milvus`、`VECTOR_STORE_MILVUS_URI=http://localhost:19530`                             | 可选后端；compose 内置三件套走 `docker compose --profile milvus up -d`（etcd + MinIO + Milvus standalone，数据落 milvus-data / minio-data / etcd-data 卷）；外部 Milvus 可加鉴权（`VECTOR_STORE_MILVUS_TOKEN` / `USERNAME` / `PASSWORD`） |
| BM25 索引    | 稀疏检索索引（增量倒排，关键词匹配）                         | `./data/bm25/default.json`（index\_name 默认 `default`）                                                                                        | 增删 O(词数) 增量维护；快照式落盘（默认每 50 次变更落盘一次 + shutdown 落盘）                                                                                                                                                              |
| 文档存储       | rag 上传的源文档                                 | `./data/documents`                                                                                                                          | DocumentRepository 存储路径                                                                                                                                                                                        |
| 日志文件       | loguru 文件轮转                                | `LOG_FILE_PATH` / `LOG_ROTATION=1 day` / `LOG_RETENTION=7 days`                                                                             | 按天轮转 / 保留 7 天（agent 侧 zip 压缩）                                                                                                                                                                                  |

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
- SQLAlchemy: <https://www.sqlalchemy.org/>
- PyMySQL: <https://pymysql.readthedocs.io/>
- APScheduler: <https://apscheduler.readthedocs.io/>
- pydantic: <https://docs.pydantic.dev/>
- loguru: <https://loguru.readthedocs.io/>
- Docker: <https://docs.docker.com/>

## 📮 联系方式

- **作者**：John Young（夜雨诗来）
- **邮箱**：<john.young@foxmail.com>
- **Gitee**：<https://gitee.com/yeyushilai>
- **GitHub**：<https://github.com/yeyushilai>
- **项目地址**：<https://github.com/chain-engine/x-QingChuan>

