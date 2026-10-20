#!/usr/bin/env python3
"""统一响应与分页 Schema（晴川 x-QingChuan，对齐北辰 schemas/common）。

约定：所有接口返回体统一为 ApiResponse[T] 包装，data 字段承载业务数据。
"""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse[T](BaseModel):
    """统一 API 响应体。"""

    code: int = Field(description="业务状态码（0 成功，非 0 为错误码）")
    message: str = Field(description="状态描述文案")
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


__all__ = ["ApiResponse", "Page"]
