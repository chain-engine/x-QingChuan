# QingChuan rag-service（qingchuan-rag）

HRSS data offline indexing + RAG (Retrieval-Augmented Generation) integrated service.
Make HRSS domain knowledge retrievable and answerable — ships an offline indexing pipeline and exposes retrieval & Q&A over HTTP + MCP dual protocols, adapted from the x-GuanHai engineering project.

[中文](README.md) | English

![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104%2B-009688?logo=fastapi&logoColor=white)
![MCP](https://img.shields.io/badge/MCP-2.3%2B-24292F)
![ChromaDB](https://img.shields.io/badge/ChromaDB-0.4%2B-F97316)
![sentence-transformers](https://img.shields.io/badge/sentence--transformers-2.2%2B-FF6F61)
![rank-bm25](https://img.shields.io/badge/rank--bm25-0.2%2B-2C3E50)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0%2B-D71F00?logo=sqlalchemy&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-8.0-4479A1?logo=mysql&logoColor=white)
![APScheduler](https://img.shields.io/badge/APScheduler-3.10%2B-2C3E50)
![Docker](https://img.shields.io/badge/Docker-24.0%2B-2496ED?logo=docker&logoColor=white)
![uv](https://img.shields.io/badge/uv-0.5%2B-6E40C9)

![Stars](https://img.shields.io/github/stars/chain-engine/x-QingChuan?label=Stars)
![Forks](https://img.shields.io/github/forks/chain-engine/x-QingChuan?label=Forks)
![License](https://img.shields.io/github/license/chain-engine/x-QingChuan?label=License)
![Commits](https://img.shields.io/github/commit-activity/m/chain-engine/x-QingChuan?label=Commits)

## 💡 Project Introduction

The HRSS data offline indexing + RAG integrated service of the QingChuan (x-QingChuan) project, listening on `:8010` by default. Core capabilities:

- **HTTP + MCP dual exit**: HTTP REST API (`/api/v1`) + MCP Streamable HTTP (`/mcp`), accessible by agents / IDEs / tools;
- **HRSS offline sync**: built-in APScheduler periodic scheduling (`SYNC_CRON` defaults to 03:00 daily) + HTTP trigger endpoint + CLI (`qingchuan-pipeline`), syncing HRSS system data into the vector store (Chroma, Milvus optional) and business DB (MySQL);
- **Full RAG pipeline**: document management (upload / delete) → text chunking → embedding (BAAI/bge-m3) → hybrid retrieval (vector + BM25 + MMR rerank) → LLM generation (with cited sources);
- **Multi-model generation**: OpenAI-compatible protocol, supporting DeepSeek / Doubao / Aliyun Bailian / Xiaomi MiMo;
- **Audit & rate limiting**: all write operations are written to audit logs (operator fixed as `internal`), built-in slowapi rate limiting.

**Current status**: the RAG retrieval pipeline runs end-to-end; HRSS sync supports mock integration (`HRSS_MOCK=true` by default).

## 🚀 Quick Start

### 🖥️ 1. Prerequisites

- **Windows / Linux / macOS** all supported; Python 3.12+ required;
- **uv** package manager (required for workspace dependency sync): <https://docs.astral.sh/uv/>;
- **Docker / Docker Compose** (needed for container deployment; optional for local development);
- **MySQL 8.0** (recommended for production; SQLite works locally, e.g. `sqlite:///./data/qingchuan.db`).

### 📥 2. Clone the Repository

```bash
git clone https://github.com/chain-engine/x-QingChuan.git
cd x-QingChuan/apps/rag-service
```

### 📦 3. Install Dependencies

Run from the repository root:

```bash
uv lock                 # first run: generate the lockfile
uv sync --package qingchuan-rag  # install rag-service and its workspace dependencies only
```

### ⚙️ 4. Environment Configuration

Copy the example files and adjust as needed (both `.env` and `config.yaml` are supported; environment variables take precedence):

```bash
cp .env.example .env
# or
cp config.yaml.example config.yaml
```

Key parameters:

| Parameter | Default | Description |
| --- | --- | --- |
| `SERVER_HOST` / `SERVER_PORT` | `0.0.0.0` / `8010` | HTTP listen address & port (MCP mounted at `/mcp`) |
| `DATABASE_URL` | `mysql+pymysql://yeyushilai:123456@localhost:3306/qingchuan` | Business DB (audit logs / sync task status); SQLite works locally |
| `SYNC_ENABLED` / `SYNC_CRON` | `false` / `0 3 * * *` | HRSS periodic sync toggle and cron expression |
| `SYNC_BATCH_SIZE` / `SYNC_INCREMENTAL` | `100` / `true` | Records per batch / incremental by default |
| `HRSS_API_URL` / `HRSS_API_TOKEN` | empty | HRSS data source URL and Bearer token (required in production) |
| `HRSS_MOCK` / `HRSS_MOCK_COUNT` | `true` / `5` | Mock mode: uses local sample data for end-to-end integration without a real API |
| `EMBEDDING_MODEL` | `BAAI/bge-m3` | embedding model (local offline inference) |
| `VECTOR_STORE_TYPE` / `VECTOR_STORE_PERSIST_DIR` | `chroma` / `./data/chroma` | vector store type (chroma / milvus) and persistence directory |
| `TEXT_SPLITTER_PROVIDER` / `TEXT_SPLITTER_STRATEGY` | `langchain` / `recursive` | chunking implementation & strategy (chunk_size 512 / overlap 50) |
| `RETRIEVAL_TOP_K` / `RETRIEVAL_SIMILARITY_THRESHOLD` | `5` / `0.7` | retrieval count / similarity threshold (`RETRIEVAL_USE_MMR` enables MMR) |
| `GENERATION_PROVIDER` / `GENERATION_MODEL` | `mimo` / `mimo-v2.6-pro` | generation model; supports DeepSeek / Doubao / Aliyun Bailian / Xiaomi MiMo |
| `DEEPSEEK_API_KEY` / `DOUBAO_API_KEY` / `ALIYUN_API_KEY` / `MIMO_API_KEY` | empty | LLM provider API keys (required in production) |
| `RATE_LIMIT_ENABLED` | `false` | slowapi rate limiting toggle (per-minute / per-hour quotas) |
| `CORS_ENABLED` / `CORS_ALLOW_ORIGINS` | `true` / `localhost:3000,8080` | CORS toggle and allowed origins |

### 🚀 5. Start the Services

**Local development with hot reload** (run inside `apps/rag-service`; hot reload follows the `DEBUG` setting):

```bash
uv run qingchuan-rag-api                # default start: listen address / port from config
uv run qingchuan-rag-api --reload       # explicitly enable hot reload (auto-restart on code change)
uv run qingchuan-rag-api --port 8010    # override the listen port
# or directly with uvicorn
uv run uvicorn qingchuan_rag.main:app --reload --host 0.0.0.0 --port 8010
```

**Docker container deployment** (run from the repository root):

```bash
docker compose up --build rag-service
```

### 🧪 6. Common Engineering Commands

```bash
uv run ruff check .            # static code check (rules aligned with x-GuanHai)
uv run ruff format .           # code formatting
uv run pytest                  # unit / integration / API tests (tests/ directory)
pre-commit run --all-files     # pre-commit hooks (ruff --fix + ruff-format)
uv audit                       # dependency vulnerability scan (built into uv 0.5+)
```

### 💬 7. Usage Examples

**RAG Q&A**:

```bash
curl -X POST http://127.0.0.1:8010/api/v1/rag/query \
  -H "Content-Type: application/json" \
  -d '{"query": "How is the social insurance contribution base determined?"}'
```

**Retrieval only, no generation**:

```bash
curl -X POST http://127.0.0.1:8010/api/v1/rag/retrieve \
  -H "Content-Type: application/json" \
  -d '{"query": "Conditions for receiving pension benefits", "top_k": 5}'
```

**Trigger an HRSS data sync**:

```bash
uv run qingchuan-pipeline sync --full
# or via HTTP
curl -X POST http://127.0.0.1:8010/api/v1/sync/trigger \
  -H "Content-Type: application/json" \
  -d '{"full": true}'
```

**MCP access**: see `scripts/qingchuan_mcp_client.py` for the MCP client example, and `scripts/qingchuan_http_client.py` for the HTTP client example.

### ❓ 8. Troubleshooting

| Symptom | Solution |
| --- | --- |
| Port already in use | Change `SERVER_PORT` (or use the `--port` launch argument) |
| `uv` install fails / times out | Check the network; this service ships with the Aliyun PyPI mirror (`[tool.uv.index]`), or configure a proxy |
| torch reports `shm.dll` missing on Windows | Keep the pinned `torch==2.12.0`; do not upgrade to 2.14.x |
| Database connection failure | Confirm MySQL is running and the database is created (`utf8mb4`); switch to SQLite locally |
| HRSS sync returns 401 / times out | Keep `HRSS_MOCK=true` during integration; for the real API, configure `HRSS_API_URL` / `HRSS_API_TOKEN` and disable mock |
| Startup fails with a config error | Invalid config blocks startup (validate); complex parameters such as `TEXT_SPLITTER_SEPARATORS` go through `config.yaml` |

## 📁 Project Structure

```text
apps/rag-service/
├── src/qingchuan_rag/
│   ├── main.py                 # FastAPI entry (HTTP routes + /mcp Streamable HTTP dual mount)
│   ├── cli.py                  # CLI: qingchuan-rag-api (HTTP launcher, supports --reload/--port/--workers)
│   ├── http_server/            # HTTP gateway (v1: health / rag / document / sync / audit)
│   ├── mcp_server/             # MCP gateway (server assembly / tools / prompts / resources)
│   ├── sync/                   # HRSS data sync (scheduler / sync_service)
│   ├── services/               # Business services (document / rag / sync / retrieval_adapter / audit)
│   ├── repositories/           # Data repositories (document / vector / bm25 / sync_task / audit_log)
│   ├── rag/                    # RAG pipeline (retrieval / augmentation / generation / pipeline)
│   ├── retrieval/              # Hybrid retrieval (candidate recall / ranking rerank / understanding)
│   ├── infras/                 # Infrastructure (database / vector / embedding / chunking / storage / bm25 / llm / http / hrss)
│   ├── models/                 # ORM entities (audit_logs / sync_tasks)
│   ├── schemas/                # Request/response schemas
│   ├── constants/              # Constants & enums (API prefix / defaults / supported doc types)
│   ├── core/                   # Core infrastructure (config / logger / exceptions / middleware)
│   └── utils/                  # Utilities (similarity / filters / index optimizer)
├── tests/                      # Unit / integration / API tests
├── scripts/                    # HTTP / MCP client example scripts
├── data/                       # Runtime data (chroma / bm25 / documents / db)
├── .env.example                # Environment variable config template
├── config.yaml.example         # YAML config template
├── Dockerfile                  # Container image (uv sync --package qingchuan-rag)
└── pyproject.toml              # qingchuan-rag (entry points: qingchuan-rag-api / qingchuan-pipeline)
```

## 🏗️ System Architecture

### 🧱 Layered Architecture

```mermaid
flowchart TB
    subgraph CLIENTS["Clients"]
        A1["HTTP Clients (REST)"]
        A2["MCP Clients (Agent / IDE / Tools)"]
    end

    subgraph GATEWAY["Gateway Layer (:8010)"]
        B1["HTTP Gateway (/api/v1)"]
        B2["MCP Gateway (/mcp Streamable HTTP)"]
    end

    subgraph SERVICE["Service Layer (services/)"]
        C1["RAG Service (query / retrieve / embed)"]
        C2["Document Service (upload / delete / index)"]
        C3["Sync Service (HRSS data)"]
        C4["Audit Service (write trail)"]
    end

    subgraph CORE["Core Pipelines"]
        D1["RAG Pipeline (retrieval / augmentation / generation)"]
        D2["Hybrid Retrieval (vector + BM25 + MMR)"]
    end

    subgraph INFRA["Infrastructure"]
        E1[("MySQL Business DB")]
        E2[("Chroma / Milvus Vector Store")]
        E3[("BM25 Sparse Index")]
        E4["LLM Provider (OpenAI-compatible)"]
        E5["HRSS Data Source (API)"]
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
    C3 -. "offline sync" .-> E5
    D1 --> E4
```

### 🔄 Core Business Flows

**HRSS offline sync → online Q&A**:

```mermaid
flowchart LR
    subgraph OFFLINE["Offline Indexing Pipeline"]
        S1["HRSS data sync<br/>(CLI / APScheduler / HTTP trigger)"] --> S2["Text chunking<br/>(langchain recursive)"]
        S2 --> S3["Embedding (bge-m3)"]
        S3 --> S4["Vector store Chroma + BM25 index"]
        S1 --> S5["Sync task status<br/>(MySQL sync_tasks)"]
    end

    subgraph ONLINE["Online Q&A"]
        Q1["User query"] --> Q2["Hybrid retrieval<br/>(vector + BM25 + MMR)"]
        Q2 --> Q3["Augmentation & rerank"]
        Q3 --> Q4["LLM generation (with sources)"]
        Q4 --> Q5["Return answer"]
    end

    S4 -.-> Q2
```

**Write operation audit trail**:

```mermaid
flowchart LR
    W["Write operations<br/>(document upload / delete, sync trigger)"] --> A["AuditService"]
    A --> L["audit_logs table<br/>(operator fixed as internal)"]
    Q["Audit query API (read-only)"] --> L
```

### 🔩 Key Technical Components

| Module | Component | Description |
| --- | --- | --- |
| Web framework | FastAPI + Uvicorn | HTTP gateway, unified response wrapper & exception handling |
| MCP | mcp 2.3+ | Streamable HTTP (/mcp), read-only retrieval tools |
| Vector retrieval | ChromaDB + sentence-transformers (BAAI/bge-m3) | Dense index; `VECTOR_STORE_TYPE` supports Milvus |
| Sparse retrieval | rank-bm25 | BM25 keyword index, hybrid with vector retrieval |
| Hybrid retrieval | candidate + ranking + understanding | Multi-path recall (vector / BM25 / keyword) + rerank (MMR / RRF / score filter) + query understanding (intent / entity / expansion / rewrite) |
| Text chunking | langchain-text-splitters | recursive / character / token / semantic strategies |
| Business DB | SQLAlchemy 2 + PyMySQL (MySQL 8) | Audit logs / sync task status |
| Scheduling | APScheduler | HRSS sync cron (default 03:00 daily) |
| LLM access | langchain-openai (OpenAI-compatible) | DeepSeek / Doubao / Aliyun Bailian / Xiaomi MiMo |
| Rate limiting | slowapi | Per-minute / per-hour quotas |
| Config | pydantic + PyYAML + python-dotenv | `.env` and `config.yaml` dual channel; invalid config blocks startup |
| Logging | loguru | Colored console / file rotation (1 day / keep 7 days) |
| Engineering | uv + ruff + pre-commit + pytest | Workspace deps, static checks, tests |

## 🛠️ Technology Stack

| Category | Choice |
| --- | --- |
| Language | Python 3.12+ |
| Web framework | FastAPI 0.104+ / Uvicorn 0.24+ |
| MCP | mcp 2.3+ (Streamable HTTP) |
| Vector database | ChromaDB 0.4+ (Milvus 2.4 / milvus-lite optional) |
| Embedding | sentence-transformers 2.2+ (BAAI/bge-m3, local offline inference) |
| Sparse retrieval | rank-bm25 0.2+ |
| Text chunking | langchain-text-splitters 1.1+ |
| LLM access | langchain-core 0.3+ / langchain-openai 0.2+ / openai 1.0+ (OpenAI-compatible protocol) |
| Business database | MySQL 8.0 (SQLAlchemy 2 + PyMySQL; SQLite for local) |
| Scheduling | APScheduler 3.10+ |
| Rate limiting | slowapi 0.1+ |
| Config management | pydantic 2.5+ / PyYAML / python-dotenv |
| Logging | loguru 0.7+ |
| Package management | uv (workspace members qingchuan-rag / qingchuan-domain) |
| Engineering | ruff + pre-commit + pytest (pytest-asyncio / pytest-cov / pytest-mock) |
| Deployment | Docker / Docker Compose |

## 📡 API Documentation

The service enables **Swagger interactive docs / ReDoc read-only docs / OpenAPI JSON**:

| Documentation | URL |
| --- | --- |
| Swagger | <http://127.0.0.1:8010/docs> |
| ReDoc | <http://127.0.0.1:8010/redoc> |
| OpenAPI JSON | <http://127.0.0.1:8010/openapi.json> |
| MCP endpoint | <http://127.0.0.1:8010/mcp> (Streamable HTTP) |

### 📋 Core API List (/api/v1)

| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/v1/health` | Health check (vector store / document store status) |
| GET | `/api/v1/version` | Version info |
| GET | `/api/v1/status` | System runtime status (uptime / vector count / document count) |
| POST | `/api/v1/rag/query` | RAG Q&A (retrieve + generate; supports top_k / threshold / MMR / metadata filter / provider override) |
| POST | `/api/v1/rag/retrieve` | Retrieval only, no generation (returns chunks & sources) |
| POST | `/api/v1/rag/embed` | Embed text |
| GET | `/api/v1/rag/stats` | RAG system statistics |
| POST | `/api/v1/documents/upload` | Upload a document and index it automatically (UTF-8 / GBK supported) |
| GET | `/api/v1/documents` | Document list (paginated, filter by status / type) |
| GET | `/api/v1/documents/{document_id}` | Document detail |
| DELETE | `/api/v1/documents/{document_id}` | Delete a document and its vectors |
| GET | `/api/v1/documents/{document_id}/status` | Document processing status |
| POST | `/api/v1/sync/trigger` | Trigger an HRSS sync (incremental by default; `full=true` full, `force=true` forced rerun) |
| GET | `/api/v1/sync/status` | Latest sync status |
| GET | `/api/v1/sync/status/{task_id}` | Sync task status by ID |
| GET | `/api/v1/audit/logs` | Audit log list (paginated by entity / action / operator / time range / keyword) |
| GET | `/api/v1/audit/logs/{log_id}` | Audit log detail |

### 🔧 MCP Tools (read-only)

| Tool | Description |
| --- | --- |
| `retrieve_docs` | Retrieve knowledge chunks most relevant to a query (supports top_k / similarity threshold / MMR / metadata filter), returns a stable `{"items": [...]}` structure |
| `rag_query` | Generate a complete answer from the knowledge base (retrieve → augment → generate), returns answer and cited chunks |

### 🔐 Permission & Access Control

- Internal service without app-level auth; all write operations (document upload / delete, sync trigger) are written to audit logs via **AuditService** with the operator fixed as `internal`; audit query endpoints are read-only;
- Built-in **slowapi rate limiting** (`RATE_LIMIT_ENABLED`, default 60 requests/minute / 1000 requests/hour);
- Invalid config blocks startup; in production keep `DEBUG=false` and tighten the CORS whitelist.

## 💾 Storage Configuration

| Storage | Purpose | Config parameters | Notes |
| --- | --- | --- | --- |
| MySQL 8.0 | Audit logs / sync task status | `DATABASE_URL` | Required in production; SQLite works locally (`sqlite:///./data/qingchuan.db`); database must be created in advance (`utf8mb4`) |
| Chroma vector store | Dense vector index (document embeddings) | `VECTOR_STORE_TYPE=chroma`、`VECTOR_STORE_PERSIST_DIR=./data/chroma`、`VECTOR_STORE_COLLECTION_NAME=documents`、`VECTOR_STORE_DISTANCE=cosine` | Persisted at `data/chroma`; Milvus optional (`VECTOR_STORE_TYPE=milvus` + `VECTOR_STORE_MILVUS_URI`) |
| BM25 index | Sparse retrieval index (keyword matching) | `./data/bm25/documents.json` | Built automatically with document indexing |
| Document storage | Uploaded source documents | `./data/documents` | DocumentRepository storage path |
| Log files | loguru file rotation | `LOG_FILE_PATH` / `LOG_ROTATION=1 day` / `LOG_RETENTION=7 days` | Rotation 1 day / retention 7 days |

Data structure definitions (ORM entities):

- `audit_logs`: operator (operator_id) / action / target (entity_type / entity_id) / result / timestamp / remark;
- `sync_tasks`: task type / status / batch / success-failure counts / timestamp.

## 📄 License

[MIT License](../LICENSE) © 2026 ChainEngine

## 📚 References

- Python: <https://www.python.org/>
- uv: <https://docs.astral.sh/uv/>
- FastAPI: <https://fastapi.tiangolo.com/>
- Uvicorn: <https://www.uvicorn.org/>
- MCP (Model Context Protocol): <https://modelcontextprotocol.io/>
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

## 📮 Contact

- **Author**: John Young（夜雨诗来）
- **Email**: john.young@foxmail.com
- **Gitee**: <https://gitee.com/yeyushilai>
- **GitHub**: <https://github.com/yeyushilai>
- **Project**: <https://github.com/chain-engine/x-QingChuan>
