#!/usr/bin/env python3
"""晴川 x-QingChuan Agent 服务入口（FastAPI，对齐北辰 server/src/main 形态）。

启动方式：
    cd apps/agent-service
    uv run uvicorn qingchuan_agent.main:app --host 0.0.0.0 --port 8020

中间件注册说明（本期骨架）：
    - 已启用：ExceptionHandlingMiddleware（统一异常）+ RequestLoggingMiddleware（访问日志）
    - 预留不接入：RequestIDMiddleware / AuthMiddleware（鉴权）/ 限流 / 熔断，
      接入时在下方取消注释即可（实现均已就绪）。
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from qingchuan_agent import (
    agents,  # noqa: F401  编排层入口：业务编排单元 + 工具注册在导入时完成
)
from qingchuan_agent.api.router import global_router
from qingchuan_agent.constants import APP_DESCRIPTION, APP_NAME, APP_VERSION
from qingchuan_agent.core.config import settings
from qingchuan_agent.core.exceptions import register_exception_handlers
from qingchuan_agent.core.logger import logger, setup_logging
from qingchuan_agent.core.middleware import ExceptionHandlingMiddleware, RequestLoggingMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动初始化 / 关闭清理。"""
    # 1. 日志初始化
    setup_logging()
    logger.info(f"{APP_NAME} 启动中，env={settings.app_env}，debug={settings.server.debug}")

    # 2. Agent 编排注册表就绪检查（懒加载，编译延迟到首次任务）
    from qingchuan_agent.agents.registry import agent_registry

    registered = [str(spec.agent_type) for spec in agent_registry.list_specs()]
    logger.info(f"Agent 注册表就绪：{registered}")

    # 3. 数据库初始化：QINGCHUAN_AGENT_DATABASE_ENABLED=true 时首次启动自动检测并创建缺失表
    #    （幂等；连接失败不阻断启动，相关接口会返回 503 提示）
    if settings.database.enabled:
        from qingchuan_agent.infras.database import init_database

        try:
            init_database()
        except Exception as exc:  # DB 失败不阻断启动
            logger.exception(f"数据库初始化失败（应用继续启动，DB 接口将返回 503）：{exc}")

    yield

    # 关闭清理
    logger.info(f"{APP_NAME} 已关闭")


def create_app() -> FastAPI:
    """构建 FastAPI 应用实例。"""
    app = FastAPI(
        title=APP_NAME,
        version=APP_VERSION,
        description=APP_DESCRIPTION,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # ── 中间件（注册顺序：后注册的先执行，倒序匹配）──
    # 预留（接入时启用）：
    #   app.add_middleware(RequestIDMiddleware)   # 请求 ID 注入
    #   app.add_middleware(AuthMiddleware)        # 鉴权（JWT）
    app.add_middleware(ExceptionHandlingMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    if settings.cors.enabled:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors.origins,
            allow_credentials=settings.cors.allow_credentials,
            allow_methods=settings.cors.allow_methods,
            allow_headers=settings.cors.allow_headers,
        )

    # ── 全局异常处理器 ──
    register_exception_handlers(app)

    # ── 路由挂载 ──
    # /api/v1/...（health / agents / tasks / events）
    app.include_router(global_router)

    return app


app = create_app()


__all__ = ["app", "create_app", "lifespan"]
