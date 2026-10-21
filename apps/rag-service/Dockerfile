# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 UV_LINK_MODE=copy

# 安装 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# 先复制清单，利用依赖层缓存
COPY pyproject.toml uv.lock ./
COPY packages/domain ./packages/domain
COPY apps/rag-service ./apps/rag-service

# 仅安装 rag-service 及其 workspace 依赖（qingchuan-rag / qingchuan-domain）
# 注意：rag 不依赖 packages/common，无需复制
RUN uv sync --package qingchuan-rag --no-dev --frozen

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8010

# 启动 HTTP 服务（LLM / 向量库等配置经环境变量注入，镜像内不含 .env；
# LLM 专用变量前缀 MIMO_* / GENERATION_*，与 agent-service 的 QINGCHUAN_AGENT_AI_LLM_* 相互独立）
CMD ["qingchuan-rag-api"]
