# QingChuan（晴川）

HRSS API offline indexing + RAG retrieval + Agent-powered Q&A platform.
Make government-domain knowledge searchable, answerable and orchestratable — built on HRSS data, exposed via dual-protocol (HTTP + MCP) services, and scheduled by LangGraph multi-agent orchestration.

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

[中文](README.md) | English

## 💡 Project Introduction

QingChuan is a **multi-agent orchestration + knowledge base empowerment platform** for HRSS (Human Resources & Social Security) business scenarios. It is structured as a uv monorepo with two independently deployable services and two shared packages:

- **rag-service（qingchuan-rag）**: integrated HRSS data offline indexing + RAG (Retrieval-Augmented Generation) service, exposing **HTTP + MCP dual protocols**; the offline indexing pipeline (CLI + APScheduler scheduled tasks) ships with the service;
- **agent-service（qingchuan-agent）**: **LangGraph multi-agent orchestration runtime** + HTTP service; the top-level orchestration graph runs `route → subagent → aggregate`, and new agents register under `agents/` to extend; it calls rag-service via MCP tools and holds no index-write permission;
- **packages/domain（qingchuan-domain）**: single source of truth for entities / schemas / retrieval protocols / ports, referenced directly by both services;
- **packages/common（qingchuan-common）**: cross-service shared components (MCP client wrapper / auth / audit / observability, placeholder).

**Current status**: the RAG retrieval pipeline runs end-to-end (HRSS sync supports mock-data integration); the Agent orchestration skeleton is delivered (new business agents extend via registration), and task/event persistence is disabled by default so the service can start without a database.

## 🚀 Quick Start

### 🖥️ 1. Prerequisites

- **Windows / Linux / macOS** all supported; Python 3.12+ required (`requires-python = ">=3.12,<3.14"`);
- **uv** package manager (required for workspace dependency sync): <https://docs.astral.sh/uv/>;
- **Docker / Docker Compose** (needed for container deployment; optional for local development);
- **MySQL 8.0** (recommended for production; local development can start without a database or use SQLite, and agent-service persistence is disabled by default).

### 📥 2. Clone the Repository

```bash
git clone https://github.com/chain-engine/x-QingChuan.git
cd x-QingChuan
```

### 📦 3. Install Dependencies

```bash
uv lock                 # first run: generate the lockfile
uv sync --all-packages  # install all workspace members (apps/* and packages/*)
```

### ⚙️ 4. Environment Configuration

Copy the example files and adjust as needed (key parameters below):

```bash
# rag-service: both .env and config.yaml are supported
cp apps/rag-service/.env.example apps/rag-service/.env
# or
cp apps/rag-service/config.yaml.example apps/rag-service/config.yaml

# agent-service: configured via .env at the repo root (prefix QINGCHUAN_AGENT_)
```

| Parameter | Default | Description |
| --- | --- | --- |
| `DATABASE_URL` | `mysql+pymysql://yeyushilai:123456@localhost:3306/qingchuan` | rag-service business database (audit / sync tasks); SQLite works locally |
| `SYNC_ENABLED` / `SYNC_CRON` | `false` / `0 3 * * *` | HRSS periodic sync toggle and cron expression |
| `HRSS_API_URL` / `HRSS_API_TOKEN` | empty | HRSS data source URL and Bearer token (required in production) |
| `HRSS_MOCK` | `true` | mock mode: uses local sample data for end-to-end integration without a real API |
| `EMBEDDING_MODEL` | `BAAI/bge-m3` | embedding model (local offline inference) |
| `VECTOR_STORE_PERSIST_DIR` | `./data/chroma` | Chroma vector store persistence directory |
| `GENERATION_PROVIDER` / `GENERATION_MODEL` | `mimo` / `mimo-v2.6-pro` | **rag-service only** generation model; supports DeepSeek / Doubao / Aliyun Bailian / Xiaomi MiMo |
| `QINGCHUAN_AGENT_AI_LLM_API_KEY` | empty (Mock) | **agent-service only** LLM API key (independent of rag-service's `MIMO_*`) |
| `QINGCHUAN_AGENT_AI_LLM_BASE_URL` | empty | agent-service LLM base URL (OpenAI-compatible, e.g. `https://api.xiaomimimo.com/v1`) |
| `QINGCHUAN_AGENT_AI_LLM_MODEL` | `deepseek-chat` | agent-service model name (e.g. `mimo-v2.6-pro`); edit only these three variables to switch provider |
| `QINGCHUAN_AGENT_DATABASE_ENABLED` | `false` | agent-service task/event persistence toggle (auto-creates tables on first start) |
| `QINGCHUAN_AGENT_RAG_HTTP_BASE_URL` | `http://rag-service:8010` | rag client base URL used by agent-service (use `http://127.0.0.1:8010` locally) |

> **LLM config separation**: the LLM for agent-service and rag-service are configured independently and never read each other's variables.
> rag-service reads `MIMO_*` / `GENERATION_*`; agent-service only reads `QINGCHUAN_AGENT_AI_LLM_*`
> (two-level nested fields require explicit reload in core/config.py; both OS env and .env are supported, OS takes precedence).
> To switch provider for either service, edit only its own block.

### 🚀 5. Start the Services

**Local development with hot reload**:

```bash
# rag-service: HTTP service (default 0.0.0.0:8010; MCP is mounted at /mcp)
uv run --package qingchuan-rag qingchuan-rag-api
# or
uv run --package qingchuan-rag uvicorn qingchuan_rag.main:app --reload --host 0.0.0.0 --port 8010

# agent-service: HTTP service (default 127.0.0.1:8020)
uv run --package qingchuan-agent qingchuan-agent-api
# or
uv run --package qingchuan-agent uvicorn qingchuan_agent.main:app --reload --host 127.0.0.1 --port 8020

# agent-service: orchestration demo (skeleton placeholder; verifies registry / routing / runtime)
uv run --package qingchuan-agent qingchuan-agent
```

**Docker container deployment**:

```bash
docker compose up --build
```

### 🧪 6. Common Engineering Commands

```bash
uv run ruff check .            # static code check
uv run ruff format .           # code formatting
uv run pytest                  # unit tests (run inside the rag-service directory)
pre-commit run --all-files     # pre-commit hooks (ruff --fix + ruff-format)
uv audit                       # dependency vulnerability scan (built into uv 0.5+)
```

### 💬 7. Usage Examples

**RAG query & answer (rag-service HTTP)**:

```bash
curl -X POST http://127.0.0.1:8010/api/v1/rag/query \
  -H "Content-Type: application/json" \
  -d '{"query": "How is the social insurance contribution base determined?"}'
```

**Trigger an HRSS data sync**:

```bash
uv run --package qingchuan-rag qingchuan-pipeline sync --full
# or via HTTP
curl -X POST http://127.0.0.1:8010/api/v1/sync/trigger \
  -H "Content-Type: application/json" \
  -d '{"full": true}'
```

**MCP retrieval**: see `apps/rag-service/scripts/qingchuan_mcp_client.py` for the MCP client example; see `apps/rag-service/scripts/qingchuan_http_client.py` for the HTTP client example.

**Submit an Agent task (agent-service)**:

```bash
curl -X POST http://127.0.0.1:8020/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{"task_type": "agent_a", "payload": {"query": "..."}}'
```

### ❓ 8. Troubleshooting

| Symptom | Solution |
| --- | --- |
| Port already in use | Change `SERVER_PORT` (rag-service) or `QINGCHUAN_AGENT_SERVER_PORT` (agent-service) |
| `uv` install fails / times out | Check the network; rag-service ships with the Aliyun PyPI mirror, or add `[tool.uv.index]` to the root `pyproject.toml` |
| torch reports `shm.dll` missing on Windows | Keep the pinned `torch==2.12.0`; do not upgrade to 2.14.x |
| Database connection failure | Confirm MySQL is running and the database is created (`utf8mb4`); agent-service can start without a DB by disabling `QINGCHUAN_AGENT_DATABASE_ENABLED` |
| HRSS sync returns 401 / times out | Keep `HRSS_MOCK=true` during integration; for the real API, configure `HRSS_API_URL` / `HRSS_API_TOKEN` and disable mock |
| Startup fails with a config error | Invalid config blocks startup (validate); in production, DEBUG / `*` CORS / memory checkpoint are rejected |

## 📁 Project Structure

```text
x-QingChuan/
├── apps/
│   ├── agent-service/                  # Agent orchestration runtime + HTTP service (standalone, :8020)
│   │   ├── src/qingchuan_agent/
│   │   │   ├── main.py                 # FastAPI entry (lifespan / middleware / exceptions / routes)
│   │   │   ├── cli.py                  # CLI: qingchuan-agent (demo) / qingchuan-agent-api
│   │   │   ├── api/                    # API layer: /api/v1 (health / version / agents / tasks / events)
│   │   │   ├── services/               # Business logic layer (AgentTaskService full lifecycle)
│   │   │   ├── repositories/           # Data access layer (task / event repositories)
│   │   │   ├── models/                 # ORM entities (AgentTask / AgentEvent)
│   │   │   ├── schemas/                # Request/response schemas (ApiResponse / Page wrappers)
│   │   │   ├── agents/                 # Orchestration layer: orchestrator / registry / runtime / base / state / routing / tools
│   │   │   ├── infras/                 # Infrastructure (MySQL Provider / LLM Provider / event bus)
│   │   │   ├── core/                   # Core infrastructure (config / logger / exceptions / middleware)
│   │   │   ├── constants/              # Constants & enums package
│   │   │   ├── templates/              # Prompt templates (LLM routing prompts)
│   │   │   └── utils/                  # Utilities (IP extraction / masking)
│   │   ├── Dockerfile
│   │   └── pyproject.toml              # qingchuan-agent
│   └── rag-service/                    # RAG service: HTTP + MCP dual protocol (standalone, :8010)
│       ├── src/qingchuan_rag/
│       │   ├── main.py                 # FastAPI entry (HTTP routes + /mcp Streamable HTTP)
│       │   ├── cli.py                  # CLI: qingchuan-rag-api / qingchuan-pipeline
│       │   ├── http_server/            # HTTP gateway (v1: health / rag / document / sync / audit_log)
│       │   ├── mcp_server/             # MCP gateway (server / tools / prompts / resources)
│       │   ├── sync/                   # HRSS data sync (scheduler / sync_service)
│       │   ├── services/               # Business services (document / rag / sync / retrieval_adapter / audit)
│       │   ├── repositories/           # Data repositories (document / vector / bm25 / sync_task / audit_log)
│       │   ├── rag/                    # RAG pipeline (retrieval / augmentation / generation / pipeline)
│       │   ├── retrieval/              # Hybrid retrieval (vector + BM25)
│       │   ├── infras/                 # Infrastructure (database / vector / embedding / chunking / storage / bm25 / llm / http / hrss)
│       │   ├── models/                 # ORM entities (audit_logs / sync_tasks)
│       │   ├── schemas/                # Request/response schemas
│       │   └── core/                   # Core infrastructure (config / logger / exceptions / middleware)
│       ├── tests/                      # Unit / integration / API tests
│       ├── scripts/                    # HTTP / MCP client scripts (qingchuan_http_client.py / qingchuan_mcp_client.py)
│       ├── data/                       # Runtime data (chroma / bm25 / documents / db)
│       ├── Dockerfile
│       └── pyproject.toml              # qingchuan-rag
├── packages/
│   ├── common/                         # Cross-service shared components (MCP client / auth / audit / observability, placeholder)
│   │   └── src/qingchuan_common/
│   └── domain/                         # Shared domain package (entities / schemas / retrieval protocols / ports, single source of truth)
│       └── src/qingchuan_domain/
├── docker-compose.yml                  # One-command orchestration of rag-service + agent-service
├── pyproject.toml                      # uv workspace root (members: apps/*, packages/*)
├── .env                                # Environment config (not committed)
├── .pre-commit-config.yaml             # pre-commit hooks (ruff)
├── LICENSE                             # MIT License
├── README.md / README.en.md            # Bilingual documentation
└── uv.lock                             # Dependency lockfile
```

## 🏗️ System Architecture

### 🧱 Layered Architecture

```mermaid
flowchart TB
    subgraph CLIENTS["Clients"]
        A1["HTTP Clients (REST)"]
        A2["MCP Clients (Agent / IDE / Tools)"]
    end

    subgraph AGENT["agent-service (qingchuan-agent, :8020)"]
        B1["API Layer (/api/v1)"]
        B2["Service Layer (services/)"]
        B3["Agent Orchestration Layer (agents/)"]
        B4["Data Access Layer (repositories/)"]
    end

    subgraph RAG["rag-service (qingchuan-rag, :8010)"]
        C1["HTTP Gateway (/api/v1)"]
        C2["MCP Gateway (/mcp)"]
        C3["Service Layer (services/)"]
        C4["Repository Layer (repositories/)"]
    end

    subgraph INFRA["Infrastructure"]
        D1[("MySQL Business DB")]
        D2[("Chroma Vector Store")]
        D3[("BM25 Sparse Index")]
        D4["LLM Provider (OpenAI-compatible)"]
        D5["HRSS Data Source (API)"]
    end

    A1 --> B1
    A2 --> C2
    B1 --> B2
    B2 --> B3
    B3 -- "MCP tool call" --> C2
    B3 --> B4
    B4 --> D1
    C1 --> C3
    C2 --> C3
    C3 --> C4
    C4 --> D1
    C4 --> D2
    C4 --> D3
    C3 --> D4
    C3 -. "offline sync" .-> D5
```

### 🔄 Core Business Flows

**Agent orchestration flow (route → subagent → aggregate)**:

```mermaid
flowchart LR
    START["Submit task"] --> ROUTE["route node<br/>(registry routing explicit / llm / hybrid)"]
    ROUTE -->|"registered agent"| SUB["subgraph node<br/>(business agent: MCP retrieve → LLM generate)"]
    SUB --> AGG["aggregate<br/>(merge events & result)"]
    AGG --> END["Return task result"]
    ROUTE -->|"unregistered / routing failed"| FAIL["Task failed (write back error)"]
    FAIL --> END
    SUB -. "interrupt (human takeover)" .-> WAIT["Waiting for human<br/>(resume continues)"]
    WAIT --> SUB
```

**RAG offline sync + online Q&A**:

```mermaid
flowchart LR
    subgraph OFFLINE["Offline Indexing Pipeline"]
        S1["HRSS data sync<br/>(CLI / APScheduler / HTTP trigger)"] --> S2["Text chunking"]
        S2 --> S3["Embedding (bge-m3)"]
        S3 --> S4["Vector store Chroma + BM25 index"]
    end

    subgraph ONLINE["Online Q&A"]
        Q1["User query"] --> Q2["Hybrid retrieval<br/>(vector + BM25 + MMR)"]
        Q2 --> Q3["Augmentation & rerank"]
        Q3 --> Q4["LLM generation (with sources)"]
        Q4 --> Q5["Return answer"]
    end

    S4 -.-> Q2
```

### 🔩 Key Technical Components

| Module | Component | Description |
| --- | --- | --- |
| Web framework | FastAPI + Uvicorn | HTTP gateway of both services, unified response wrapper & exception handling |
| Agent orchestration | LangGraph | Top-level orchestration graph + nested business subgraphs, interrupt / resume |
| Registration / routing | AgentRegistry | task_type → AgentSpec mapping-table routing, lazy compile cache |
| LLM access | LangChain (OpenAI-compatible) | DeepSeek / Doubao / Aliyun Bailian / Xiaomi MiMo |
| MCP | mcp 2.3+ | rag-service Streamable HTTP (/mcp); agent calls via MCP client |
| Vector retrieval | ChromaDB + sentence-transformers (BAAI/bge-m3) | Dense index, persisted at `data/chroma` |
| Sparse retrieval | rank-bm25 | BM25 index, hybrid with vector retrieval |
| Business DB | SQLAlchemy 2 + PyMySQL (MySQL 8) | Audit logs / sync tasks / Agent tasks & events |
| Scheduling | APScheduler | HRSS sync cron (default 03:00 daily) |
| Config | pydantic-settings / pydantic + PyYAML | Segmented prefixed config; invalid config blocks startup |
| Logging | loguru | Colored console / file rotation (1 day / keep 7 days) |
| Engineering | uv + ruff + pre-commit + pytest | Workspace deps, static checks, tests |
| Deployment | Docker Compose | One-command orchestration of rag-service + agent-service |

## 🛠️ Technology Stack

| Category | Choice |
| --- | --- |
| Language | Python 3.12+ |
| Web framework | FastAPI 0.115+ / Uvicorn 0.30+ |
| Agent orchestration | LangGraph 0.2+ (top-level graph + business subgraphs, interrupt / resume) |
| LLM access | LangChain (langchain-core 0.3+ / langchain-openai 0.2+, OpenAI-compatible protocol) |
| MCP | mcp 2.3+ (Streamable HTTP) |
| Vector database | ChromaDB 0.4+ |
| Embedding | sentence-transformers (BAAI/bge-m3) |
| Sparse retrieval | rank-bm25 0.2+ |
| Business database | MySQL 8.0 (SQLAlchemy 2 + PyMySQL; SQLite for local) |
| Scheduling | APScheduler 3.10+ |
| Config management | pydantic-settings 2.5+ / pydantic 2.9+ / PyYAML |
| Logging | loguru 0.7+ |
| Package management | uv (workspace: apps/* + packages/*, uv.lock) |
| Engineering | ruff + pre-commit + pytest (pytest-asyncio / pytest-cov) |
| Deployment | Docker / Docker Compose |

## 📡 API Documentation

Both services enable **Swagger interactive docs / ReDoc read-only docs / OpenAPI JSON**:

| Service | Swagger | ReDoc | OpenAPI JSON | MCP endpoint |
| --- | --- | --- | --- | --- |
| rag-service (:8010) | <http://127.0.0.1:8010/docs> | <http://127.0.0.1:8010/redoc> | <http://127.0.0.1:8010/openapi.json> | <http://127.0.0.1:8010/mcp> (Streamable HTTP) |
| agent-service (:8020) | <http://127.0.0.1:8020/docs> | <http://127.0.0.1:8020/redoc> | <http://127.0.0.1:8020/openapi.json> | — (calls rag-service via MCP client) |

### 📋 Core API List

**agent-service (/api/v1, 9 endpoints)**:

| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/v1/health` | Health check (incl. DB / Agent runtime status) |
| GET | `/api/v1/version` | Version info |
| GET | `/api/v1/agents/specs` | Registered agent specs |
| POST | `/api/v1/tasks` | Submit an Agent task (explicit task_type routing / empty → LLM dynamic routing) |
| GET | `/api/v1/tasks` | Task list (paginated) |
| GET | `/api/v1/tasks/{id}` | Task detail |
| POST | `/api/v1/tasks/{id}/resume` | Human takeover: resume an interrupted task |
| GET | `/api/v1/events` | Collaboration event list (paginated) |
| GET | `/api/v1/events/{id}` | Event detail |

**rag-service (/api/v1, core subset)**:

| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/v1/health` / `/version` / `/status` | Health / version / system status |
| POST | `/api/v1/rag/query` | RAG Q&A (retrieve + generate) |
| POST | `/api/v1/rag/retrieve` | Text retrieval only (no generation; returns chunks & sources) |
| POST | `/api/v1/rag/embed` | Embed text |
| GET | `/api/v1/rag/stats` | RAG system statistics |
| POST | `/api/v1/documents/upload` | Upload a document and index it automatically |
| GET | `/api/v1/documents` | Document list (paginated) |
| GET | `/api/v1/documents/{document_id}` | Document detail |
| DELETE | `/api/v1/documents/{document_id}` | Delete a document and its vectors |
| GET | `/api/v1/documents/{document_id}/status` | Document processing status |
| POST | `/api/v1/sync/trigger` | Trigger an HRSS sync (incremental by default; `full=true` for full) |
| GET | `/api/v1/sync/status` | Latest sync status |
| GET | `/api/v1/sync/status/{task_id}` | Sync task status by ID |
| GET | `/api/v1/audit/logs` | Audit log list (paginated) |
| GET | `/api/v1/audit/logs/{log_id}` | Audit log detail |

**MCP tools (rag-service, read-only)**:

| Tool | Description |
| --- | --- |
| `retrieve_docs` | Retrieve knowledge chunks most relevant to a query (supports top_k / similarity threshold / MMR / metadata filter) |
| `rag_query` | Generate a complete answer from the knowledge base (retrieve → augment → generate), returns answer and cited chunks |

### 🔐 Permission & Access Control

- **agent-service**: the tool center follows the principle of "read-only tools are directly callable, write operations require human execution"; task routing supports explicit / llm / hybrid modes; production (`APP_ENV=production`) enforces validation — DEBUG forbidden, CORS whitelist cannot be `*`, checkpoint must be redis;
- **rag-service**: built-in slowapi rate limiting (`RATE_LIMIT_ENABLED` / per-minute / per-hour quotas); all write operations (document upload / delete, sync trigger) are written to audit logs with the fixed operator `internal`; audit endpoints are read-only.

## 💾 Storage Configuration

| Storage | Purpose | Config parameters | Notes |
| --- | --- | --- | --- |
| MySQL 8.0 | rag-service: audit logs / sync task status; agent-service: Agent tasks / events | `DATABASE_URL` / `QINGCHUAN_AGENT_DATABASE_*` | Required in production; SQLite or no-DB works locally (agent-service disabled by default) |
| Chroma vector store | Dense vector index (document embeddings) | `VECTOR_STORE_PERSIST_DIR=./data/chroma`, `VECTOR_STORE_COLLECTION_NAME`, `VECTOR_STORE_DISTANCE` | Persisted at `apps/rag-service/data/chroma` |
| BM25 index | Sparse retrieval index (keyword matching) | `./data/bm25/documents.json` | Built automatically with document indexing |
| Document storage | Uploaded source documents | `./data/documents` | DocumentRepository storage path |
| Log files | loguru file rotation | `LOG_FILE_PATH` / `QINGCHUAN_AGENT_LOGGING_FILE_PATH` | Rotation 1 day / retention 7 days / zip compression |

Data structure definitions (ORM entities):

- **rag-service**: `audit_logs` (operator / action / target / result / timestamp), `sync_tasks` (type / status / batch / success-failure counts);
- **agent-service**: `agent_tasks` (task_type / payload / status / result / error / thread ID), `agent_events` (event type / payload / related task).

## 📄 License

[MIT License](LICENSE) © 2026 ChainEngine

## 📚 References

- Python: <https://www.python.org/>
- uv: <https://docs.astral.sh/uv/>
- FastAPI: <https://fastapi.tiangolo.com/>
- Uvicorn: <https://www.uvicorn.org/>
- LangGraph: <https://langchain-ai.github.io/langgraph/>
- LangChain: <https://python.langchain.com/>
- MCP (Model Context Protocol): <https://modelcontextprotocol.io/>
- ChromaDB: <https://docs.trychroma.com/>
- sentence-transformers: <https://www.sbert.net/>
- rank-bm25: <https://github.com/dorianbrown/rank_bm25>
- SQLAlchemy: <https://www.sqlalchemy.org/>
- PyMySQL: <https://pymysql.readthedocs.io/>
- APScheduler: <https://apscheduler.readthedocs.io/>
- pydantic: <https://docs.pydantic.dev/>
- loguru: <https://loguru.readthedocs.io/>
- Docker: <https://docs.docker.com/>

## 📮 Contact

- **Author**: John Young（夜雨诗来）
- **Email**: john.young@foxmail.com
- **Gitee**: <https://gitee.com/yeyushilai>
- **GitHub**: <https://github.com/yeyushilai>
- **Project**: <https://github.com/chain-engine/x-QingChuan>
