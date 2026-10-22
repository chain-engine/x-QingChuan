#!/usr/bin/env python3
"""
Middleware Module

中间件模块：实现CORS、限流、请求ID追踪等
"""

import time
import uuid
from collections.abc import Callable

from fastapi import Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

from qingchuan_rag.constants import HeaderType
from qingchuan_rag.core.config import settings
from qingchuan_rag.core.logger import logger

# 限流器实例
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[
        f"{settings.RATE_LIMIT_REQUESTS_PER_MINUTE}/minute",
        f"{settings.RATE_LIMIT_REQUESTS_PER_HOUR}/hour",
    ],
)


async def request_id_middleware(request: Request, call_next: Callable) -> Response:
    """请求ID中间件

    为每个请求生成唯一的请求ID，并通过 loguru contextualize 注入日志上下文，
    使一条请求从头到尾的所有日志都携带同一个 request_id（JSON 日志同字段）。
    """
    request_id: str = request.headers.get(HeaderType.REQUEST_ID.mark) or str(uuid.uuid4())
    request.state.request_id = request_id

    with logger.contextualize(request_id=request_id):
        response: Response = await call_next(request)
        response.headers[HeaderType.REQUEST_ID.mark] = request_id

        logger.info(f"Request {request_id}: {request.method} {request.url.path}")
    return response


async def logging_middleware(request: Request, call_next: Callable) -> Response:
    """日志中间件

    记录请求和响应的详细信息
    """
    start_time: float = time.time()
    request.state.start_time = start_time

    response: Response = await call_next(request)

    process_time: float = (time.time() - start_time) * 1000
    request_id: str = getattr(request.state, "request_id", "unknown")

    logger.info(
        f"Request {request_id} completed in {process_time:.2f}ms with status {response.status_code}"
    )

    return response


def get_cors_origins() -> list[str]:
    """获取CORS允许的来源"""
    cors_origins: str = getattr(settings, "CORS_ALLOW_ORIGINS", "*")
    if cors_origins == "*":
        return ["*"]
    return [origin.strip() for origin in cors_origins.split(",")]


def setup_cors_middleware(app) -> None:
    """配置CORS中间件"""
    if not getattr(settings, "CORS_ENABLED", True):
        return

    allow_origins = get_cors_origins()
    allow_credentials = settings.cors.allow_credentials

    # 与 agent-service 校验对齐：生产环境禁止通配来源（任意源 + 凭证 = 安全风险）
    if settings.SERVER_ENVIRONMENT == "production" and "*" in allow_origins:
        raise ValueError("生产环境 CORS_ALLOW_ORIGINS 不能为 *，请显式配置允许的域名列表")

    # 通配来源与凭证互斥：浏览器禁止 ACAO:* 携带凭证，且"任意源+凭证"等于任意站点可携凭证请求
    if "*" in allow_origins and allow_credentials:
        logger.warning(
            "CORS allow_origins 包含 *，自动关闭 allow_credentials（通配来源与凭证互斥）"
        )
        allow_credentials = False

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def setup_middleware(app) -> None:
    """配置所有中间件"""
    setup_cors_middleware(app)

    # 添加限流状态到request.state
    app.state.limiter = limiter
    app.state._rate_limit_exceeded_handler = _rate_limit_exceeded_handler

    # HTTP中间件（最后添加的最先执行）
    app.middleware("http")(logging_middleware)
    app.middleware("http")(request_id_middleware)
