# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 UV_LINK_MODE=copy
# 显式指定国内 PyPI 镜像（pyproject 的 [[tool.uv.index]] 已默认 aliyun，此处双保险，
# 防止构建环境未按预期读取项目索引配置时回落国外源）
ENV UV_DEFAULT_INDEX=https://mirrors.aliyun.com/pypi/simple/

# 安装 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# 先复制清单，利用依赖层缓存
COPY pyproject.toml uv.lock ./
COPY packages/domain ./packages/domain
COPY packages/common ./packages/common
COPY apps/rag-service ./apps/rag-service

# 仅安装 rag-service 及其 workspace 依赖（qingchuan-rag / qingchuan-domain / qingchuan-common）
# 注：统一响应信封沉淀于 qingchuan_common.http.response，rag 依赖 packages/common，必须复制
# BuildKit cache mount：已下载的 wheel 持久缓存到 /root/.cache/uv，依赖层失效后增量拉取，避免全量重下
RUN --mount=type=cache,target=/root/.cache/uv uv sync --package qingchuan-rag --no-dev --frozen

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8010

# 启动 HTTP 服务（LLM / 向量库等配置经环境变量注入，镜像内不含 .env；
# LLM 专用变量前缀 MIMO_* / GENERATION_*，与 agent-service 的 QINGCHUAN_AGENT_AI_LLM_* 相互独立）
CMD ["qingchuan-rag-api"]
