#!/usr/bin/env python3
"""
中间件模块（晴川 x-QingChuan，对齐北辰 core/middleware 写法）
提供 HTTP 请求处理中间件：
    - RequestIDMiddleware：请求 ID 注入（生产级特性，默认预留不注册）
    - RequestLoggingMiddleware：全链路请求记录
    - ExceptionHandlingMiddleware：统一异常处理（404/405/500）
    - AuthMiddleware：认证中间件基础封装（预留，暂不接入）

骨架 main.py 默认只注册 ExceptionHandling + RequestLogging；
RequestID / Auth / 限流 / 熔断 等生产级中间件保留实现，接入时在 API 层取消注册。
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable

from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from qingchuan_agent.constants import HttpHeaders
from qingchuan_agent.core.logger import logger

# 敏感请求头黑名单，日志中始终脱敏
_SENSITIVE_HEADERS: frozenset[str] = frozenset(
    {"authorization", "cookie", "set-cookie", "x-api-key", "x-auth-token", "x-csrftoken"}
)


def _get_client_ip(request: Request) -> str:
    """提取客户端 IP（对齐北辰 utils.helpers.get_client_ip 职责）。"""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client is not None else "-"


def _mask_sensitive(headers: dict[str, str], keys: list[str]) -> dict[str, str]:
    """对敏感请求头脱敏（对齐北辰 utils.helpers.mask_sensitive 职责）。"""
    return {k: "***" if k.lower() in keys else v for k, v in headers.items()}


def _middleware_error_response(request: Request, code: int, message: str) -> JSONResponse:
    """中间件兜底错误响应（与 core/exceptions 同构，core 层不反向依赖 api 层）。"""
    from datetime import UTC, datetime

    body: dict[str, object] = {
        "code": code,
        "message": message,
        "data": None,
        "timestamp": datetime.now(UTC).isoformat(),
        "request_id": getattr(request.state, "request_id", None),
    }
    return JSONResponse(status_code=code, content=body)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """请求 ID 中间件。
    为每个请求生成唯一 UUID，注入 request.state.request_id，并在响应头返回 X-Request-ID。
    使用 logger.contextualize() 将 request_id 注入 loguru 上下文，该请求作用域内所有日志自动携带。
    """

    def __init__(self, app: ASGIApp, header_name: str = HttpHeaders.X_REQUEST_ID.mark) -> None:
        super().__init__(app)
        self.header_name: str = header_name

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id: str | None = request.headers.get(self.header_name)
        if not request_id:
            request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        with logger.contextualize(request_id=request_id):
            response: Response = await call_next(request)
            response.headers[self.header_name] = request_id
            return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """全链路请求记录：路径、入参、响应耗时、客户端 IP。敏感字段自动脱敏。"""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start_time: float = time.time()
        request_id: str = getattr(request.state, "request_id", "-")
        client_ip: str = _get_client_ip(request)
        full_url: str = str(request.url)
        query_params: dict[str, str] = dict(request.query_params)
        safe_headers = _mask_sensitive(dict(request.headers), keys=list(_SENSITIVE_HEADERS))
        logger.bind(request_id=request_id).info(
            f"Request started: {request.method} {full_url} from {client_ip} "
            f"query={query_params} headers={safe_headers}"
        )
        response: Response = await call_next(request)
        elapsed: float = (time.time() - start_time) * 1000
        logger.bind(request_id=request_id).info(
            f"Request completed: {request.method} {full_url} "
            f"status={response.status_code} duration={elapsed:.2f}ms"
        )
        return response


class ExceptionHandlingMiddleware(BaseHTTPMiddleware):
    """统一异常处理中间件。全局拦截 HTTPException 与未捕获异常，标准化返回。"""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            return await call_next(request)
        except HTTPException as exc:
            request_id: str = getattr(request.state, "request_id", "-")
            logger.bind(request_id=request_id).warning(
                f"HTTP exception: {exc.status_code} {exc.detail}"
            )
            return _middleware_error_response(request, exc.status_code, str(exc.detail))
        except Exception as exc:
            request_id = getattr(request.state, "request_id", "-")
            logger.bind(request_id=request_id).exception(f"Unhandled exception: {exc}")
            return _middleware_error_response(request, 500, "Internal server error")


class AuthMiddleware(BaseHTTPMiddleware):
    """认证中间件基础封装（预留）。
    验证 Authorization 头；可配置跳过路径列表。完整 JWT/OAuth 校验接入认证服务后启用。
    """

    def __init__(
        self,
        app: ASGIApp,
        skip_paths: list[str] | None = None,
        token_validator: Callable[[str], bool] | None = None,
    ) -> None:
        super().__init__(app)
        self.skip_paths: list[str] = skip_paths or [
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/v1/health",
            "/api/v1/version",
        ]
        self.token_validator: Callable[[str], bool] | None = token_validator

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if any(request.url.path.startswith(path) for path in self.skip_paths):
            return await call_next(request)
        authorization: str | None = request.headers.get("Authorization")
        if not authorization or not authorization.strip():
            from qingchuan_agent.core.exceptions import UnauthorizedError

            raise UnauthorizedError("Missing Authorization header")
        if self.token_validator is not None:
            token: str = (
                authorization[7:].strip()
                if authorization.lower().startswith("bearer ")
                else authorization
            )
            if not self.token_validator(token):
                from qingchuan_agent.core.exceptions import UnauthorizedError

                raise UnauthorizedError("Invalid token")
        return await call_next(request)


__all__ = [
    "AuthMiddleware",
    "ExceptionHandlingMiddleware",
    "RequestIDMiddleware",
    "RequestLoggingMiddleware",
]
