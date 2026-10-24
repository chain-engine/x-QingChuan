# 晴川（QingChuan）部署指南

本文档面向**阿里云 ECS 生产部署**（Docker Compose 方式）。
部署形态：Docker Compose 编排 + 根目录 `.env` 注入凭据 + 容器健康检查，敏感信息不落镜像/代码。

---

## 1. 部署架构与端口规划

| 端口 | 服务 | 用途 | 说明 |
| --- | --- | --- | --- |
| 13306 | mysql | 运维口（可选） | 服务间走 compose 内部网络，如无需外部直连可去掉 `ports` |
| 16379 | redis | 运维口（可选） | 同上 |
| — | milvus（etcd + minio + standalone） | 向量库，仅内部网络 | rag-service 经 `http://milvus:19530` 访问，不暴露宿主端口 |
| **8010** | rag-service | **对外服务口（安全组放行）** | MCP 挂 `/mcp`，HTTP 挂 `/api/v1` |
| **8020** | agent-service | **对外服务口（安全组放行）** | HTTP 挂 `/api/v1` |

> mysql / redis / milvus（etcd + minio + standalone）/ rag-service / agent-service 全部由本 compose 编排，内部网络互通，不依赖宿主机其他服务。
> 数据卷 `mysql-data` / `redis-data` / `etcd-data` / `minio-data` / `milvus-data` / `rag-data` / `agent-logs` / `rag-logs` 持久化，容器重建不丢数据。

**阿里云 ECS 安全组需放行**：`8010`、`8020`（如开放运维口再加 `13306`、`16379`；建议运维口仅对管理员 IP 开放）。

---

## 2. 前置条件

- 阿里云 ECS：4 核 8G 及以上（rag-service 为 torch 推理，Milvus standalone 预留 4G 内存）
- Docker Engine + Docker Compose v2
- 仓库代码部署在 `/opt/x-QingChuan`（与现有服务同目录惯例）

---

## 3. 部署步骤

### 3.1 拉取代码

```bash
cd /opt
git clone https://github.com/chain-engine/x-QingChuan.git
cd /opt/x-QingChuan
```

### 3.2 准备环境文件

```bash
cat > .env <<'EOF'
# 部署凭据（生产请改为强密码）
MYSQL_ROOT_PASSWORD=change-me-root-password
MYSQL_DATABASE=qingchuan
MYSQL_USER=qingchuan
MYSQL_PASSWORD=change-me-db-password
REDIS_PASSWORD=change-me-redis-password
# MinIO（Milvus 对象存储组件）root 凭据（compose 必填，生产用强密码）
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=change-me-minio-password
# Agent 服务 LLM（前缀 QINGCHUAN_AGENT_AI_LLM_，与 RAG 的 MIMO_* 相互独立）
QINGCHUAN_AGENT_AI_LLM_API_KEY=sk-your-key
QINGCHUAN_AGENT_AI_LLM_BASE_URL=https://api.xiaomimimo.com/v1
QINGCHUAN_AGENT_AI_LLM_MODEL=mimo-v2.6-pro
# RAG 服务 LLM（小米 Mimo）
MIMO_API_KEY=sk-your-key
MIMO_API_BASE=https://api.xiaomimimo.com/v1
MIMO_MODEL_NAME=mimo-v2.6-pro
# RAG 向量存储：compose 部署时 rag-service 内部固定连 http://milvus:19530（内置 Milvus standalone），
# 此处 VECTOR_STORE_MILVUS_URI 仅用于本地 uv run 调试（连本机 Milvus 服务 http://localhost:19530）
VECTOR_STORE_TYPE=milvus
VECTOR_STORE_MILVUS_URI=http://localhost:19530
VECTOR_STORE_COLLECTION_NAME=documents
VECTOR_STORE_DISTANCE=cosine
VECTOR_STORE_DIMENSION=1024
EOF
```

也可直接 `cp .env.example .env` 后编辑（完整键清单见 `.env.example`）。

必填/常用键说明：

| 键 | 说明 |
| --- | --- |
| `MYSQL_ROOT_PASSWORD` / `MYSQL_USER` / `MYSQL_PASSWORD` | 业务库账号密码（必填，生产用强密码） |
| `REDIS_PASSWORD` | Redis 密码（必填，生产用强密码） |
| `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` | Milvus 对象存储组件 MinIO 凭据（`MINIO_ROOT_PASSWORD` 必填，生产用强密码） |
| `MIMO_API_KEY` | rag-service 大模型密钥（小米 Mimo） |
| `QINGCHUAN_AGENT_AI_LLM_API_KEY` | agent-service 大模型密钥（独立于 RAG） |
| `QINGCHUAN_AGENT_CORS_ORIGINS` | agent 允许的跨域来源（生产禁 `*`；pydantic list 类型须用 **JSON 数组**格式，如 `["https://admin.example.com"]`；默认 localhost 开发白名单） |
| `SYNC_ENABLED` / `HRSS_API_URL` / `HRSS_API_TOKEN` | 人社数据源周期同步（按需开启） |

### 3.3 确认端口与磁盘

```bash
ss -lntp | grep -E ':(8010|8020|13306|16379)'   # 应无输出
df -h /                                          # 需剩余 8G+（两个镜像约 4.5G）
```

### 3.4 构建并启动

```bash
docker compose up -d --build
```

- `mysql` / `redis` / `etcd` / `minio` / `milvus` 先启动并通过健康检查（mysql/redis 约 30s，milvus 首次启动约 90s+），`rag-service`、`agent-service` 随后启动
- agent-service 以生产模式运行（`QINGCHUAN_AGENT_APP_ENV=production`），强制启用 Redis + redis checkpoint
- 首次构建 rag 镜像较大（CPU-only torch，约 3.5GB），视服务器带宽需 5~20 分钟
- 首次启动自动建表（幂等）：审计日志 / 同步任务 / 文档元数据

### 3.5 验证部署

```bash
docker compose ps          # 7 个容器全部 healthy（etcd/minio/milvus 需等待 start_period）
curl -s http://localhost:8010/api/v1/health
curl -s http://localhost:8020/api/v1/health
```

浏览器访问 `http://<ECS公网IP>:8010/docs` 可见 rag 的 Swagger 文档，即公网放行成功。

### 3.6 安全组放行

阿里云控制台 → 实例 → 安全组 → 入方向规则，添加两条：

| 协议 | 端口范围 | 访问来源 | 描述 |
| --- | --- | --- | --- |
| 自定义 TCP | `8010/8010` | `0.0.0.0/0`（或本机 IP/32） | qingchuan-rag |
| 自定义 TCP | `8020/8020` | `0.0.0.0/0`（或本机 IP/32） | qingchuan-agent |

### 3.7 停止 / 清理

```bash
docker compose down          # 停止，保留数据卷
docker compose down -v       # 彻底清理（含 mysql/redis/milvus 数据，慎用）
```

---

## 4. 运维

### 4.1 日志

- 容器 stdout 日志：`docker logs -f x-QingChuan-agent` / `x-QingChuan-rag`（json-file 轮转 10m×3）
- 应用文件日志（挂卷持久化）：
  - agent：`agent-logs` 卷，容器内 `/app/apps/agent-service/logs/`
  - rag：`rag-logs` 卷，容器内 `/app/apps/rag-service/logs/`

### 4.2 数据持久化与备份

| 数据 | 存储位置 | 备份方式 |
| --- | --- | --- |
| MySQL（审计/任务/文档元数据） | `mysql-data` 卷 | `mysqldump` 或卷快照 |
| Redis（checkpoint/事件总线） | `redis-data` 卷 | 非核心，可重建 |
| Milvus 向量库 | `milvus-data` 卷（+ `etcd-data` / `minio-data` 元数据与对象存储卷） | 三卷一并快照（milvus 数据跨 etcd/minio 强依赖） |
| 文档对象存储 | `rag-data` 卷（`/app/data/documents`） | 卷快照 |

### 4.3 升级

```bash
cd /opt/x-QingChuan
git pull
docker compose up -d --build
docker compose ps    # 确认全部 healthy
```

### 4.4 常见问题

| 现象 | 处理 |
| --- | --- |
| `docker compose up` 报 `VAR is required` | `.env` 缺键，按 3.2 补齐 |
| agent-service 启动失败提示生产校验 | 检查 `.env` 中 Redis 密码与 compose 一致、`QINGCHUAN_AGENT_AGENT_CHECKPOINT=redis` 已生效 |
| rag-service 健康检查失败 | `docker compose logs rag-service` 查看；多为向量库初始化或 MySQL 连接问题 |
| `docker compose` 命令不存在 | 使用 `docker-compose`（v1）或安装 compose v2 插件 |
