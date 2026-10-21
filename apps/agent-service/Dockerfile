# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 UV_LINK_MODE=copy

# 安装 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# 先复制清单，利用依赖层缓存
COPY pyproject.toml uv.lock ./
COPY packages/domain ./packages/domain
COPY packages/common ./packages/common
COPY apps/agent-service ./apps/agent-service

# 仅安装 agent-service 及其 workspace 依赖（qingchuan-agent / qingchuan-common / qingchuan-domain）
RUN uv sync --package qingchuan-agent --no-dev --frozen

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8020

# 启动 HTTP 服务（LLM / 数据库等配置经环境变量注入，镜像内不含 .env；
# LLM 专用变量前缀 QINGCHUAN_AGENT_AI_LLM_，与 rag-service 的 MIMO_* 相互独立）
CMD ["qingchuan-agent-api"]
