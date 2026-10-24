"""统一 HTTP 响应工具（晴川 x-QingChuan 跨服务通用件）。

agent-service 与 rag-service 共用同一套响应信封与构造函数：
    - ApiResponse[T]  统一响应体（code / message / data / timestamp / request_id）
    - Page[T]         通用分页结果
    - success_response / error_response  统一 JSONResponse 构造函数

早期两服务各自实现（agent ApiResponse 含 timestamp、rag ResponseModel 无 timestamp），
本模块收敛为单一实现，消除字段差异与重复代码；默认状态码取自共享领域包 HttpStatus。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, TypeVar

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from qingchuan_domain.constants.enums import HttpStatus

T = TypeVar("T")


class ApiResponse[T](BaseModel):
    """统一 API 响应体（code 语义为 HTTP 状态码，如 200 成功）。"""

    code: int = Field(default=HttpStatus.OK.value, description="HTTP 状态码")
    message: str = Field(default=HttpStatus.OK.desc, description="状态描述文案")
    data: T | None = Field(default=None, description="业务数据，无数据时为 null")
    timestamp: str = Field(description="响应时间戳（ISO8601）")
    request_id: str | None = Field(
        default=None, description="请求 ID（中间件注入，骨架阶段可为 null）"
    )


class Page[T](BaseModel):
    """通用分页结果。"""

    items: list[T] = Field(description="当前页数据列表")
    total: int = Field(description="总数")
    page: int = Field(description="当前页码（从 1 开始）")
    page_size: int = Field(description="每页条数")


def _build_response(
    *,
    data: Any,
    request: Request,
    code: int,
    message: str,
) -> JSONResponse:
    """按统一信封构造 JSONResponse。"""
    payload = ApiResponse[object](
        code=code,
        message=message,
        data=data,
        timestamp=datetime.now(UTC).isoformat(),
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json", exclude_none=False)
    return JSONResponse(status_code=code, content=payload)


def success_response(
    data: Any,
    request: Request,
    code: int = HttpStatus.OK.value,
    message: str = HttpStatus.OK.desc,
) -> JSONResponse:
    """构造统一成功响应。

    Args:
        data: 业务数据（dict 或已 model_dump 的结果）
        request: 当前请求对象（用于提取 request_id）
        code: HTTP 状态码
        message: 响应描述

    Returns:
        JSONResponse: 统一格式的成功响应
    """
    return _build_response(data=data, request=request, code=code, message=message)


def error_response(
    request: Request,
    code: int = HttpStatus.INTERNAL_SERVER_ERROR.value,
    message: str = HttpStatus.INTERNAL_SERVER_ERROR.desc,
    data: Any = None,
) -> JSONResponse:
    """构造统一错误响应。

    Args:
        request: 当前请求对象（用于提取 request_id）
        code: HTTP 状态码
        message: 错误描述
        data: 附加错误详情（如校验错误列表、details 等），默认 None

    Returns:
        JSONResponse: 统一格式的错误响应
    """
    return _build_response(data=data, request=request, code=code, message=message)


__all__ = ["ApiResponse", "Page", "error_response", "success_response"]
