#!/usr/bin/env python3
"""
统一异常处理模块（晴川 x-QingChuan，对齐 rag-service core/exceptions 写法）。

异常类单一事实来源在共享领域包 qingchuan_domain.exceptions（跨服务一致）；
本模块仅 re-export，保证 agent 内部既有导入路径不变，并保留全局异常处理器：
    AppException
    ├── BusinessError (4xx)
    │   ├── ValidationError       (400)
    │   ├── UnauthorizedError     (401)
    │   ├── ForbiddenError        (403)
    │   ├── NotFoundError         (404)
    │   ├── ConflictError         (409)
    │   ├── RateLimitError        (429)
    │   └── AgentException        (400，Agent 编排专属)
    └── SystemError (5xx)
        ├── DatabaseError         (500)
        └── ExternalServiceError  (502)
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from qingchuan_domain.exceptions import (
    AgentException,
    AppException,
    BusinessError,
    ConfigurationError,
    ConflictError,
    DatabaseError,
    DocumentError,
    EmbeddingError,
    ExternalServiceError,
    ForbiddenError,
    GenerationError,
    NotFoundError,
    RateLimitError,
    RetrievalError,
    SyncError,
    SystemError,
    UnauthorizedError,
    ValidationError,
    VectorStoreError,
)

from qingchuan_agent.constants import ApiResponseMessage, HttpStatus


async def _app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """处理所有 AppException 及其子类。生产环境 5xx 不透出 detail。"""
    from qingchuan_agent.core.config import settings
    from qingchuan_agent.core.logger import logger

    request_id: str | None = getattr(request.state, "request_id", None)
    log_level: str = "ERROR" if exc.code >= 500 else "WARNING"
    logger.bind(request_id=request_id or "-").log(log_level, f"{type(exc).__name__}: {exc.message}")
    show_details = exc.code < 500 or settings.is_development
    data: dict[str, Any] | None = None
    if exc.detail is not None and show_details:
        data = {"details": exc.detail}
    return _build_error_json(request, exc.code, exc.message, data)


async def _validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """处理 Pydantic 请求校验异常。"""
    from qingchuan_agent.core.logger import logger

    request_id: str | None = getattr(request.state, "request_id", None)
    errors = exc.errors()
    logger.bind(request_id=request_id or "-").warning(f"Validation error: {errors}")
    return _build_error_json(
        request,
        code=422,
        message=ApiResponseMessage.VALIDATION_ERROR.mark,
        data={"details": errors},
    )


async def _http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """处理 FastAPI/Starlette 原生 HTTPException（依赖层 503、路由未匹配等）。

    统一转换为 ApiResponse 结构，避免 FastAPI 默认 {"detail": ...} 透出。
    """
    from qingchuan_agent.core.logger import logger

    request_id: str | None = getattr(request.state, "request_id", None)
    logger.bind(request_id=request_id or "-").warning(
        f"HTTP exception: {exc.status_code} {exc.detail}"
    )
    detail: Any = exc.detail
    if isinstance(detail, dict):
        message: str = str(detail.get("message") or detail)
        data: dict[str, Any] | None = {"detail": detail}
    else:
        message = str(detail)
        data = None
    return _build_error_json(request, exc.status_code, message, data)


async def _generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """处理所有未捕获异常的兜底处理器。"""
    from qingchuan_agent.core.logger import logger

    request_id: str | None = getattr(request.state, "request_id", None)
    logger.bind(request_id=request_id or "-").exception(f"Unhandled exception: {exc}")
    return _build_error_json(
        request,
        code=HttpStatus.INTERNAL_SERVER_ERROR.mark,
        message=HttpStatus.INTERNAL_SERVER_ERROR.desc,
    )


def _build_error_json(
    request: Request,
    code: int,
    message: str,
    data: dict[str, Any] | None = None,
) -> JSONResponse:
    """构造统一错误响应体（与 api/response 同构，core 层不反向依赖 api 层）。"""
    body: dict[str, Any] = {
        "code": code,
        "message": message,
        "data": data,
        "timestamp": datetime.now(UTC).isoformat(),
        "request_id": getattr(request.state, "request_id", None),
    }
    return JSONResponse(status_code=code, content=body)


def register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器：AppException → HTTPException → ValidationError → Exception 兜底。"""
    app.add_exception_handler(AppException, _app_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(HTTPException, _http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _generic_exception_handler)


__all__ = [
    # 异常类（re-export qingchuan_domain.exceptions）
    "AgentException",
    "AppException",
    "BusinessError",
    "ConfigurationError",
    "ConflictError",
    "DatabaseError",
    "DocumentError",
    "EmbeddingError",
    "ExternalServiceError",
    "ForbiddenError",
    "GenerationError",
    "NotFoundError",
    "RateLimitError",
    "RetrievalError",
    "SyncError",
    "SystemError",
    "UnauthorizedError",
    "ValidationError",
    "VectorStoreError",
    # 处理器
    "register_exception_handlers",
]
