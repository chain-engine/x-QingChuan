#!/usr/bin/env python3
"""
Exceptions Module

全局异常定义（re-export 共享领域包 qingchuan_domain.exceptions）。
异常类的单一事实来源在 packages/domain，跨服务（rag-service / agent-service）
保持一致；本模块仅做转发，保证 rag-service 内既有导入路径不变。
"""

from qingchuan_domain.exceptions import (
    AppException,
    BusinessError,
    ConfigurationError,
    ConflictError,
    DatabaseError,
    DocumentError,
    EmbeddingError,
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

__all__ = [
    "AppException",
    "BusinessError",
    "SystemError",
    "NotFoundError",
    "ValidationError",
    "UnauthorizedError",
    "ForbiddenError",
    "ConflictError",
    "RateLimitError",
    "DocumentError",
    "SyncError",
    "EmbeddingError",
    "VectorStoreError",
    "RetrievalError",
    "GenerationError",
    "DatabaseError",
    "ConfigurationError",
]
