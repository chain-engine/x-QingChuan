#!/usr/bin/env python3
"""
HTTP 响应工具
提供统一的 JSONResponse 构造函数，避免各路由模块重复样板代码。

Functions:
    success_response: 构造统一成功响应
    error_response: 构造统一错误响应
"""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from qingchuan_rag.constants import HttpStatus
from qingchuan_rag.schemas.responses import ResponseModel


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
    payload = ResponseModel(
        code=code,
        message=message,
        data=data,
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json", exclude_none=False)
    return JSONResponse(status_code=code, content=payload)


def error_response(
    request: Request,
    code: int = HttpStatus.INTERNAL_ERROR.value,
    message: str = HttpStatus.INTERNAL_ERROR.desc,
    data: Any = None,
) -> JSONResponse:
    """构造统一错误响应。

    Args:
        request: 当前请求对象（用于提取 request_id）
        code: HTTP 状态码
        message: 错误描述
        data: 附加错误详情（如校验错误列表、detail 等），默认 None

    Returns:
        JSONResponse: 统一格式的错误响应
    """
    payload = ResponseModel(
        code=code,
        message=message,
        data=data,
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json", exclude_none=False)
    return JSONResponse(status_code=code, content=payload)


__all__ = ["success_response", "error_response"]
