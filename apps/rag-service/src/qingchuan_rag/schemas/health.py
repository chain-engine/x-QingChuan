#!/usr/bin/env python3
"""
Health Schema Module

健康检查相关接口的请求和响应模型
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from qingchuan_rag.core.config import settings


class HealthCheckRequest(BaseModel):
    """健康检查请求"""

    pass

    model_config = ConfigDict(
        json_schema_extra={"example": {}},
    )


class HealthCheckResponse(BaseModel):
    """健康检查响应"""

    status: str = Field(..., description="服务状态", examples=["healthy"])
    version: str = Field(..., description="版本号", examples=["0.1.0"])
    timestamp: datetime = Field(..., description="时间戳")
    checks: dict[str, Any] = Field(
        default_factory=dict,
        description="各项检查结果",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "version": "0.1.0",
                "timestamp": "2024-01-01T00:00:00.000000Z",
                "checks": {
                    "database": "healthy",
                    "cache": "healthy",
                },
            }
        },
    )


class VersionResponse(BaseModel):
    """版本信息响应"""

    version: str = Field(..., description="版本号")
    name: str = Field(..., description="项目名称")
    description: str = Field(..., description="项目描述")
    python_version: str = Field(..., description="Python版本")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "version": settings.APP_VERSION,
                "name": settings.APP_ID,
                "description": settings.APP_DESCRIPTION,
                "python_version": "3.11",
            }
        },
    )


class StatusResponse(BaseModel):
    """系统状态响应"""

    status: str = Field(..., description="系统状态")
    uptime: float = Field(..., description="运行时间（秒）")
    memory_usage: dict[str, int] = Field(
        default_factory=dict,
        description="内存使用情况",
    )
    vector_count: int = Field(default=0, description="向量数量")
    document_count: int = Field(default=0, description="文档数量")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "running",
                "uptime": 3600.0,
                "memory_usage": {"rss": 1024000},
                "vector_count": 1000,
                "document_count": 100,
            }
        },
    )
