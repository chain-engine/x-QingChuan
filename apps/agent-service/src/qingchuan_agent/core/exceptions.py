#!/usr/bin/env python3
"""
统一异常处理模块（晴川 x-QingChuan，对齐北辰 core/exceptions 写法）
定义异常层级结构与全局异常处理器。所有自定义异常继承 AppException：
    AppException
    ├── BusinessException (4xx)
    │   ├── ValidationException     (422)
    │   ├── AuthenticationException (401)
    │   ├── AuthorizationException  (403)
    │   ├── NotFoundException       (404)
    │   └── ConflictException       (409)
    ├── AgentException       (400，Agent 编排异常)
    └── SystemException (5xx)
        ├── DatabaseException       (500)
        └── ExternalServiceException(502)
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from qingchuan_agent.constants import ApiResponseMessage, HttpStatusCode


class AppException(Exception):
    """应用异常基类。"""

    def __init__(
        self,
        message: str = "Application error",
        code: int = HttpStatusCode.INTERNAL_SERVER_ERROR.mark,
        details: Any | None = None,
        error_code: str | None = None,
    ) -> None:
        self.message: str = message
        self.code: int = code
        self.details: Any | None = details
        self.error_code: str | None = error_code
        super().__init__(self.message)


class BusinessException(AppException):
    """业务异常基类（4xx）。"""

    def __init__(
        self,
        message: str = "Business error",
        code: int = HttpStatusCode.BAD_REQUEST.mark,
        details: Any | None = None,
        error_code: str | None = None,
    ) -> None:
        super().__init__(message=message, code=code, details=details, error_code=error_code)


class ValidationException(BusinessException):
    """参数校验异常（422）。"""

    def __init__(
        self,
        message: str = "Validation error",
        details: Any | None = None,
        error_code: str | None = None,
    ) -> None:
        super().__init__(message=message, code=422, details=details, error_code=error_code)


class AuthenticationException(BusinessException):
    """认证异常（401）。"""

    def __init__(
        self,
        message: str = "Authentication failed",
        details: Any | None = None,
        error_code: str | None = None,
    ) -> None:
        super().__init__(message=message, code=401, details=details, error_code=error_code)


class AuthorizationException(BusinessException):
    """授权异常（403）。"""

    def __init__(
        self,
        message: str = "Permission denied",
        details: Any | None = None,
        error_code: str | None = None,
    ) -> None:
        super().__init__(message=message, code=403, details=details, error_code=error_code)


class NotFoundException(BusinessException):
    """资源未找到异常（404）。"""

    def __init__(
        self,
        message: str = "Resource not found",
        details: Any | None = None,
        error_code: str | None = None,
    ) -> None:
        super().__init__(message=message, code=404, details=details, error_code=error_code)


class ConflictException(BusinessException):
    """资源冲突异常（409）。"""

    def __init__(
        self,
        message: str = "Resource conflict",
        details: Any | None = None,
        error_code: str | None = None,
    ) -> None:
        super().__init__(message=message, code=409, details=details, error_code=error_code)


class AgentException(BusinessException):
    """Agent 编排异常（400 系列，Agent 任务提交 / 路由 / 执行失败）。"""

    def __init__(
        self,
        message: str = "Agent orchestration error",
        details: Any | None = None,
        error_code: str | None = None,
    ) -> None:
        super().__init__(message=message, code=400, details=details, error_code=error_code)


class SystemException(AppException):
    """系统异常基类（5xx）。"""

    def __init__(
        self,
        message: str = HttpStatusCode.INTERNAL_SERVER_ERROR.desc,
        code: int = HttpStatusCode.INTERNAL_SERVER_ERROR.mark,
        details: Any | None = None,
        error_code: str | None = None,
    ) -> None:
        super().__init__(message=message, code=code, details=details, error_code=error_code)


class DatabaseException(SystemException):
    """数据库异常（500）。"""

    def __init__(
        self,
        message: str = "Database error",
        details: Any | None = None,
        error_code: str | None = None,
    ) -> None:
        super().__init__(message=message, code=500, details=details, error_code=error_code)


class ExternalServiceException(SystemException):
    """外部服务异常（502）。"""

    def __init__(
        self,
        message: str = "External service error",
        details: Any | None = None,
        error_code: str | None = None,
    ) -> None:
        super().__init__(message=message, code=502, details=details, error_code=error_code)


async def _app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """处理所有 AppException 及其子类。生产环境 5xx 不透出 details。"""
    from qingchuan_agent.core.config import settings
    from qingchuan_agent.core.logger import logger

    request_id: str | None = getattr(request.state, "request_id", None)
    log_level: str = "ERROR" if exc.code >= 500 else "WARNING"
    logger.bind(request_id=request_id or "-").log(log_level, f"{type(exc).__name__}: {exc.message}")
    show_details = exc.code < 500 or settings.is_development
    data: dict[str, Any] | None = None
    if exc.details is not None and show_details:
        data = {"details": exc.details}
    if exc.error_code:
        data = {"error_code": exc.error_code, **(data or {})}
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
        code=HttpStatusCode.INTERNAL_SERVER_ERROR.mark,
        message=HttpStatusCode.INTERNAL_SERVER_ERROR.desc,
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
    "AgentException",
    "AppException",
    "AuthenticationException",
    "AuthorizationException",
    "BusinessException",
    "ConflictException",
    "DatabaseException",
    "ExternalServiceException",
    "NotFoundException",
    "SystemException",
    "ValidationException",
    "register_exception_handlers",
]
