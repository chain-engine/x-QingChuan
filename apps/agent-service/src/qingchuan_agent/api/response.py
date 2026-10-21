#!/usr/bin/env python3
"""API 响应工具（晴川 x-QingChuan，对齐北辰 api/response）。

提供统一的 JSONResponse 构造函数，避免各路由模块重复样板代码：
    success_response: 构造统一成功响应
    error_response: 构造统一错误响应
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from qingchuan_agent.constants import HttpStatus
from qingchuan_agent.schemas.common import ApiResponse


def success_response(
    data: Any,
    request: Request,
    code: int = HttpStatus.OK.mark,
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
    payload = ApiResponse[object](
        code=code,
        message=message,
        data=data,
        timestamp=datetime.now(UTC).isoformat(),
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json", exclude_none=False)
    return JSONResponse(status_code=code, content=payload)


def error_response(
    request: Request,
    code: int = HttpStatus.INTERNAL_SERVER_ERROR.mark,
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
    payload = ApiResponse[object](
        code=code,
        message=message,
        data=data,
        timestamp=datetime.now(UTC).isoformat(),
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json", exclude_none=False)
    return JSONResponse(status_code=code, content=payload)


__all__ = ["error_response", "success_response"]
