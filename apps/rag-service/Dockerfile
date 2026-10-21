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

# 仅安装 rag-service 及其 workspace 依赖
RUN uv sync --package qingchuan-rag --no-dev --frozen

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8010

CMD ["qingchuan-rag-api"]
