#!/usr/bin/env python3
"""
RAG Schema Module

RAG相关接口的请求和响应模型。

RAG 问答 / 检索的数据契约以共享领域包 qingchuan_domain 为单一事实来源：
    - RAGQueryRequest / RAGQueryResponse / from_search_results → qingchuan_domain.schemas.rag
    - RetrievalQuery / RetrievalResponse / RetrievedChunk         → qingchuan_domain.schemas.retrieval
本模块仅保留 rag-service 本地独有 DTO（Embedding / Generation 嵌入与生成内部接口）。
"""


from pydantic import BaseModel, ConfigDict, Field

from qingchuan_domain.schemas.rag import RAGQueryRequest, RAGQueryResponse, from_search_results
from qingchuan_domain.schemas.retrieval import RetrievalQuery, RetrievalResponse, RetrievedChunk
from qingchuan_rag.constants import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_TEMPERATURE,
    DEFAULT_TIMEOUT,
)

__all__ = [
    "EmbeddingRequest",
    "EmbeddingResponse",
    "GenerationRequest",
    "GenerationResponse",
    "RAGQueryRequest",
    "RAGQueryResponse",
    "RetrievalQuery",
    "RetrievalResponse",
    "RetrievedChunk",
    "RetrievedDocument",
    "from_search_results",
]


RetrievedDocument = RetrievedChunk
"""检索命中片段（领域契约别名；单一事实来源 qingchuan_domain.schemas.retrieval.RetrievedChunk）。

保留本别名保证 rag 既有导入路径不变；HTTP 与 MCP 响应均序列化为领域契约结构。
"""


class EmbeddingRequest(BaseModel):
    """向量化请求"""

    texts: list[str] = Field(
        ...,
        min_length=1,
        description="待向量化的文本列表",
    )
    normalize: bool = Field(
        default=True,
        description="是否归一化",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "texts": ["文本1", "文本2"],
                "normalize": True,
            }
        },
    )


class GenerationRequest(BaseModel):
    """生成请求"""

    prompt: str = Field(
        ...,
        min_length=1,
        max_length=8000,
        description="生成提示",
    )
    context: list[str] = Field(
        default_factory=list,
        description="上下文文本",
    )
    provider: str | None = Field(
        default=None,
        description="LLM提供商",
    )
    temperature: float = Field(
        default=DEFAULT_TEMPERATURE,
        ge=0.0,
        le=2.0,
        description="温度参数",
    )
    max_tokens: int = Field(
        default=DEFAULT_MAX_TOKENS,
        ge=1,
        le=8000,
        description="最大token数",
    )
    timeout: int = Field(
        default=DEFAULT_TIMEOUT,
        ge=1,
        le=300,
        description="超时时间（秒）",
    )


class EmbeddingResponse(BaseModel):
    """向量化响应"""

    embeddings: list[list[float]] = Field(..., description="向量列表")
    dimension: int = Field(..., description="向量维度")
    model: str = Field(..., description="使用的模型")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "embeddings": [[0.1, 0.2, 0.3]],
                "dimension": 1024,
                "model": "BAAI/bge-m3",
            }
        },
    )


class GenerationResponse(BaseModel):
    """生成响应"""

    text: str = Field(..., description="生成的文本")
    provider: str = Field(..., description="使用的LLM提供商")
    model: str = Field(..., description="使用的模型")
    tokens_used: int | None = Field(
        default=None,
        description="使用的token数",
    )
    finish_reason: str | None = Field(
        default=None,
        description="结束原因",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "text": "这是生成的文本...",
                "provider": "mimo",
                "model": "mimo-v2.6-pro",
                "tokens_used": 500,
                "finish_reason": "stop",
            }
        },
    )
