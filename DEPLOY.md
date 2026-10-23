# 晴川（QingChuan）阿里云部署指南

本文档面向**阿里云单机生产部署**，与已部署的汉江（x-HanJiang）项目**共存于同一台主机**。
部署形态对齐汉江：Docker Compose 编排 + 根目录 `.env` 注入凭据 + 容器健康检查，全部敏感信息不落镜像/代码。

---

## 1. 部署架构与端口规划

单机内两个项目并存，端口规划如下（**汉江已占用 80 / 3307 / 6380，晴川全部避开**）：

| 端口 | 归属 | 用途 | 说明 |
| --- | --- | --- | --- |
| 80 | 汉江 nginx | 汉江统一入口 | 晴川不占用 |
| 3307 / 6380 | 汉江 mysql / redis | 汉江运维口 | 晴川不占用 |
| **13306** | 晴川 mysql | 运维口（可选） | 服务间走 compose 内部网络，如无需外部直连可去掉 `ports` |
| **16379** | 晴川 redis | 运维口（可选） | 同上 |
| **8010** | 晴川 rag-service | **对外服务口（安全组放行）** | MCP 挂 `/mcp`，HTTP 挂 `/api/v1` |
| **8020** | 晴川 agent-service | **对外服务口（安全组放行）** | HTTP 挂 `/api/v1` |

> 容器命名均带 `x-QingChuan-` 前缀，与汉江（`x-HanJiang-`）不冲突；两个 compose 各自创建独立 bridge 网络，互不干扰。
> 同库共用：晴川 mysql（13306）、redis（16379）均为本 compose 自管，不依赖宿主机/汉江的数据库实例。

**阿里云 ECS 安全组需放行**：`8010`、`8020`（如开放运维口再加 `13306`、`16379`；建议运维口仅对管理员 IP 开放）。

---

## 2. 前置条件

- 阿里云 ECS：2 核 4G 及以上（rag-service 为 torch 推理，建议 4 核 8G）
- Docker Engine + Docker Compose v2（与汉江相同的运行环境）
- 仓库代码（部署机直接 `git clone` 或拉取最新 commit）

---

## 3. 部署步骤

### 3.1 准备环境文件

```bash
cd x-QingChuan
cp .env.example .env
vim .env   # 填写以下必填项与密钥
```

`.env` 必填/常用键（完整清单见 `.env.example`）：

| 键 | 说明 |
| --- | --- |
| `MYSQL_ROOT_PASSWORD` | 晴川 MySQL root 密码（必填，勿与汉江共用） |
| `MYSQL_USER` / `MYSQL_PASSWORD` | 晴川业务库账号密码（必填） |
| `REDIS_PASSWORD` | 晴川 Redis 密码（必填） |
| `MIMO_API_KEY` | rag-service 大模型密钥（小米 Mimo） |
| `QINGCHUAN_AGENT_AI_LLM_API_KEY` | agent-service 大模型密钥（独立于 RAG） |
| `QINGCHUAN_AGENT_CORS_ORIGINS` | agent 允许的跨域来源（生产禁 `*`；pydantic list 类型须用 **JSON 数组**格式，如 `["https://admin.example.com"]`；默认 localhost 开发白名单） |
| `SYNC_ENABLED` / `HRSS_API_URL` / `HRSS_API_TOKEN` | 人社数据源周期同步（按需开启） |

### 3.2 构建并启动

```bash
docker compose up -d --build
```

- `mysql` / `redis` 先启动并通过健康检查（约 30s），`rag-service`、`agent-service` 随后启动
- agent-service 以生产模式运行（`QINGCHUAN_AGENT_APP_ENV=production`），强制启用 Redis + redis checkpoint
- 首次启动自动建表（幂等）：审计日志 / 同步任务 / 文档元数据

### 3.3 验证部署

```bash
# 容器健康状态（4 个服务均应为 healthy）
docker compose ps

# 服务探针
curl -s http://localhost:8010/api/v1/health
curl -s http://localhost:8020/api/v1/health

# 首次使用：导入人社政策种子文档（可选，将 data 目录 JSON 迁移入库）
docker compose exec rag-service qingchuan-pipeline migrate-documents
```

### 3.4 停止 / 清理

```bash
docker compose down          # 停止，保留数据卷
docker compose down -v       # 彻底清理（含 mysql/redis/rag 数据，慎用）
```

---

## 4. 运维

### 4.1 日志

- 容器 stdout 日志：`docker logs -f x-QingChuan-agent` / `x-QingChuan-rag`（json-file 轮转 10m×3）
- 应用文件日志（挂卷持久化）：
  - agent：`docker volume` 挂载的 `agent-logs`，容器内路径 `/app/apps/agent-service/logs/`
  - rag：`rag-logs` 卷，容器内路径 `/app/apps/rag-service/logs/`

### 4.2 数据持久化

| 数据 | 存储位置 | 备份方式 |
| --- | --- | --- |
| MySQL（审计/任务/文档元数据） | `mysql-data` 卷 | `mysqldump` 或卷快照 |
| Redis（checkpoint/事件总线） | `redis-data` 卷 | 非核心，可重建 |
| 向量库 + 文档对象存储 | `rag-data` 卷（`/app/data`） | 卷快照（含 milvus.db 与 documents/） |

### 4.3 升级

```bash
git pull
docker compose up -d --build
docker compose ps    # 确认全部 healthy
```

### 4.4 常见问题

| 现象 | 处理 |
| --- | --- |
| `docker compose up` 报 `VAR is required` | `.env` 缺键，按 3.1 补齐 |
| agent-service 启动失败提示生产校验 | 检查 `.env` 中 Redis 密码与 compose 一致、`QINGCHUAN_AGENT_AGENT_CHECKPOINT=redis` 已生效 |
| rag-service 健康检查失败 | `docker compose logs rag-service` 查看；多为向量库初始化或 MySQL 连接问题 |
| 与汉江端口冲突 | 晴川已避开 80/3307/6380；如仍有冲突调整 `MYSQL_HOST_PORT` / `REDIS_HOST_PORT` |

---

## 5. 与汉江共存的注意点

1. **凭据隔离**：晴川与汉江使用各自的 MySQL/Redis 实例与密码，不要复用汉江的 `MYSQL_PASSWORD` / `REDIS_PASSWORD`
2. **端口隔离**：晴川 13306/16379/8010/8020 与汉江 3307/6380/80 不冲突；`docker compose ps` 可同时看到两个项目的容器
3. **资源预留**：汉江 app 限 2 核 1G，晴川 rag 限 2 核 2G / agent 限 1 核 1G，两项目叠加需主机满足 4 核 8G 及以上
4. **安全组**：只放行必要端口；若为同一安全组，尽量将晴川运维口（13306/16379）仅对管理员 IP 开放
