#!/usr/bin/env python3
"""
Document Schema Module

文档管理相关接口的请求和响应模型

文档状态 / 类型字段绑定本地枚举（DocStatus / DocType），
入参模型开启 use_enum_values 以保持字符串语义兼容（入库值即枚举 mark）。
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from qingchuan_rag.constants import DocStatus, DocType


class DocumentUploadRequest(BaseModel):
    """文档上传请求"""

    file_type: DocType = Field(
        ...,
        description="文档类型",
        examples=["txt"],
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="文档元数据",
    )

    model_config = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "file_type": "txt",
                "metadata": {"author": "John Doe"},
            }
        },
    )


class DocumentDeleteRequest(BaseModel):
    """文档删除请求"""

    document_id: str = Field(
        ...,
        description="文档ID",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "document_id": "550e8400-e29b-41d4-a716-446655440000",
            }
        },
    )


class DocumentQueryRequest(BaseModel):
    """文档查询请求"""

    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页记录数")
    status: DocStatus | None = Field(default=None, description="文档状态")
    file_type: DocType | None = Field(default=None, description="文档类型")

    model_config = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "page": 1,
                "page_size": 20,
                "status": "completed",
                "file_type": "txt",
            }
        },
    )


class DocumentInfo(BaseModel):
    """文档信息"""

    document_id: str = Field(..., description="文档ID")
    file_name: str = Field(..., description="文件名")
    file_type: DocType = Field(..., description="文件类型")
    file_size: int = Field(..., description="文件大小（字节）")
    status: DocStatus = Field(..., description="文档状态")
    chunk_count: int = Field(..., description="分块数量")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="元数据",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "document_id": "550e8400-e29b-41d4-a716-446655440000",
                "file_name": "document.txt",
                "file_type": "txt",
                "file_size": 1024,
                "status": "completed",
                "chunk_count": 10,
                "created_at": "2024-01-01T00:00:00.000000Z",
                "updated_at": "2024-01-01T00:00:00.000000Z",
                "metadata": {},
            }
        },
    )


class DocumentUploadResponse(BaseModel):
    """文档上传响应"""

    document_id: str = Field(..., description="文档ID")
    file_name: str = Field(..., description="文件名")
    status: DocStatus = Field(..., description="处理状态")
    message: str = Field(..., description="消息")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "document_id": "550e8400-e29b-41d4-a716-446655440000",
                "file_name": "document.txt",
                "status": "completed",
                "message": "Document uploaded successfully",
            }
        },
    )


class DocumentDeleteResponse(BaseModel):
    """文档删除响应"""

    document_id: str = Field(..., description="文档ID")
    status: DocStatus = Field(..., description="删除状态")
    message: str = Field(..., description="消息")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "document_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "deleted",
                "message": "Document deleted successfully",
            }
        },
    )


class DocumentQueryResponse(BaseModel):
    """文档查询响应"""

    total: int = Field(..., description="总记录数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页记录数")
    total_pages: int = Field(..., description="总页数")
    items: list[DocumentInfo] = Field(..., description="文档列表")

    model_config = ConfigDict(
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


class DocumentStatusResponse(BaseModel):
    """文档状态响应"""

    document_id: str = Field(..., description="文档ID")
    file_name: str = Field(..., description="文件名")
    status: DocStatus = Field(..., description="文档状态")
    chunk_count: int = Field(..., description="分块数量")
    vector_count: int = Field(..., description="向量数量")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "document_id": "550e8400-e29b-41d4-a716-446655440000",
                "file_name": "document.txt",
                "status": "completed",
                "chunk_count": 10,
                "vector_count": 10,
            }
        },
    )
