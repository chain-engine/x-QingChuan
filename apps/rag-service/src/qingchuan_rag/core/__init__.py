#!/usr/bin/env python3
"""
Core Package

核心支撑层：配置、日志、异常、容器、响应封装
"""

# 注意：logger和config不从此导入，避免循环依赖
# 请直接从具体模块导入：from core.logger import logger
#                                     from core.config import settings

from qingchuan_rag.core.exceptions import (
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
    SystemError,
    UnauthorizedError,
    ValidationError,
    VectorStoreError,
)

__all__ = [
    # Config
    "Settings",
    "settings",
    # Logger
    "logger",
    # Exceptions
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
    "EmbeddingError",
    "VectorStoreError",
    "RetrievalError",
    "GenerationError",
    "DatabaseError",
    "ConfigurationError",
]
