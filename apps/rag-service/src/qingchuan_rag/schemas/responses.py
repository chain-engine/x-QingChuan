#!/usr/bin/env python3
"""
Response Schema Module

统一响应格式定义
"""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from qingchuan_rag.constants import HttpStatus

T = TypeVar("T")


class ResponseModel(BaseModel, Generic[T]):
    """通用响应模型

    标准API响应结构
    """

    code: int = Field(default=HttpStatus.OK.value, description="响应状态码", examples=[200])
    message: str = Field(default="success", description="响应消息", examples=["success"])
    data: T | None = Field(default=None, description="响应数据")
    request_id: str | None = Field(default=None, description="请求ID")

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "code": 200,
                "message": "success",
                "data": {"key": "value"},
                "request_id": "550e8400-e29b-41d4-a716-446655440000",
            }
        },
    )


class PageModel(BaseModel, Generic[T]):
    """分页响应模型

    用于列表数据的分页响应
    """

    total: int = Field(..., description="总记录数", examples=[100])
    page: int = Field(..., description="当前页码", examples=[1])
    page_size: int = Field(..., description="每页记录数", examples=[20])
    total_pages: int = Field(..., description="总页数", examples=[5])
    items: list[T] = Field(..., description="数据列表")

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "total": 100,
                "page": 1,
                "page_size": 20,
                "total_pages": 5,
                "items": [],
            }
        },
    )


class ErrorDetail(BaseModel):
    """错误详情模型"""

    field: str | None = Field(default=None, description="错误字段", examples=["email"])
    message: str = Field(..., description="错误消息", examples=["Invalid email format"])
    type: str = Field(..., description="错误类型", examples=["ValueError"])


class ErrorResponse(BaseModel):
    """错误响应模型"""

    code: int = Field(..., description="错误状态码", examples=[400])
    message: str = Field(..., description="错误消息", examples=["Bad Request"])
    errors: list[ErrorDetail] | None = Field(default=None, description="错误详情列表")
    request_id: str | None = Field(default=None, description="请求ID")

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "code": 400,
                "message": "Bad Request",
                "errors": [
                    {
                        "field": "email",
                        "message": "Invalid email format",
                        "type": "ValueError",
                    }
                ],
                "request_id": "550e8400-e29b-41d4-a716-446655440000",
            }
        },
    )


def success_response(
    data: Any = None,
    message: str = "success",
    code: int = HttpStatus.OK.value,
    request_id: str | None = None,
) -> dict[str, Any]:
    """构造成功响应"""
    return {
        "code": code,
        "message": message,
        "data": data,
        "request_id": request_id,
    }


def error_response(
    message: str,
    code: int = 500,
    errors: list[ErrorDetail] | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """构造错误响应"""
    return {
        "code": code,
        "message": message,
        "errors": errors,
        "request_id": request_id,
    }
