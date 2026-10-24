#!/usr/bin/env python3
"""
Schemas Package

统一存放接口请求入参、响应返回Pydantic模型。

RAG 检索 / 问答契约以共享领域包 qingchuan_domain 为单一事实来源，
本包 re-export 供既有导入路径使用（RAGQueryRequest / RAGQueryResponse /
RetrievalQuery / RetrievalResponse / RetrievedChunk / RetrievedDocument）。
"""

from qingchuan_rag.schemas.base import (
    BaseRequest,
    BaseResponse,
    BaseSchema,
)
from qingchuan_rag.schemas.document import (
    DocumentDeleteRequest,
    DocumentDeleteResponse,
    DocumentInfo,
    DocumentQueryRequest,
    DocumentQueryResponse,
    DocumentStatusResponse,
    DocumentUploadRequest,
    DocumentUploadResponse,
)
from qingchuan_rag.schemas.health import (
    HealthCheckRequest,
    HealthCheckResponse,
    StatusResponse,
    VersionResponse,
)
from qingchuan_rag.schemas.rag import (
    EmbeddingRequest,
    EmbeddingResponse,
    GenerationRequest,
    GenerationResponse,
    RAGQueryRequest,
    RAGQueryResponse,
    RetrievalQuery,
    RetrievalResponse,
    RetrievedChunk,
    RetrievedDocument,
)
from qingchuan_rag.schemas.responses import (
    PageModel,
    ResponseModel,
)

__all__ = [
    # Base
    "BaseSchema",
    "BaseRequest",
    "BaseResponse",
    # Responses
    "ResponseModel",
    "PageModel",
    # RAG
    "RAGQueryRequest",
    "RetrievalQuery",
    "EmbeddingRequest",
    "GenerationRequest",
    "RetrievedDocument",
    "RetrievedChunk",
    "RAGQueryResponse",
    "EmbeddingResponse",
    "RetrievalResponse",
    "GenerationResponse",
    # Document
    "DocumentUploadRequest",
    "DocumentDeleteRequest",
    "DocumentQueryRequest",
    "DocumentInfo",
    "DocumentUploadResponse",
    "DocumentDeleteResponse",
    "DocumentQueryResponse",
    "DocumentStatusResponse",
    # Health
    "HealthCheckRequest",
    "HealthCheckResponse",
    "VersionResponse",
    "StatusResponse",
]
