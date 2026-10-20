#!/usr/bin/env python3
"""
Base Schema Module

基础Schema定义，提供通用字段和配置
"""

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class BaseSchema(BaseModel):
    """基础Schema类

    提供所有Schema的通用配置
    """

    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "created_at": "2024-01-01T00:00:00.000000Z",
                "updated_at": "2024-01-01T00:00:00.000000Z",
            }
        },
    )


class BaseRequest(BaseModel):
    """基础请求模型

    所有请求模型的基类
    """

    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
        json_schema_extra={"example": {}},
    )


class BaseResponse(BaseModel, Generic[T]):
    """基础响应模型

    所有响应模型的基类，包含通用字段
    """

    code: int = Field(default=200, description="响应状态码")
    message: str = Field(default="success", description="响应消息")
    data: T | None = Field(default=None, description="响应数据")
    request_id: str | None = Field(default=None, description="请求追踪ID")

    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
        json_schema_extra={
            "example": {
                "code": 200,
                "message": "success",
                "data": None,
                "request_id": "550e8400-e29b-41d4-a716-446655440000",
            }
        },
    )
