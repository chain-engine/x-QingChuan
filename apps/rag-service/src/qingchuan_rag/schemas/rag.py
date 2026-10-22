#!/usr/bin/env python3
"""
RAG Schema Module

RAG相关接口的请求和响应模型
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from qingchuan_domain.schemas.retrieval import RetrievedChunk
from qingchuan_rag.constants import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_MMR_LAMBDA,
    DEFAULT_SIMILARITY_THRESHOLD,
    DEFAULT_TEMPERATURE,
    DEFAULT_TIMEOUT,
    DEFAULT_TOP_K,
)


class RAGQueryRequest(BaseModel):
    """RAG查询请求"""

    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="用户查询内容，支持中英文",
        examples=["什么是RAG？"],
    )
    top_k: int = Field(
        default=DEFAULT_TOP_K,
        ge=1,
        le=20,
        description="返回相关文档数量，默认5",
        examples=[5],
    )
    similarity_threshold: float = Field(
        default=DEFAULT_SIMILARITY_THRESHOLD,
        ge=0.0,
        le=1.0,
        description="相似度阈值，低于该值的文档被过滤，默认0.7",
        examples=[0.7],
    )
    use_mmr: bool = Field(
        default=False,
        description="是否使用MMR算法增加结果多样性",
        examples=[False],
    )
    mmr_lambda: float = Field(
        default=DEFAULT_MMR_LAMBDA,
        ge=0.0,
        le=1.0,
        description="MMR参数，0.0=多样性优先，1.0=相关性优先",
        examples=[0.5],
    )
    metadata_filter: dict[str, Any] | None = Field(
        default=None,
        description='元数据过滤条件，如 {"file_type": "pdf"}',
        examples=[None],
    )
    provider: str | None = Field(
        default=None,
        description="LLM提供商，为空使用默认",
        examples=[None],
    )
    temperature: float = Field(
        default=DEFAULT_TEMPERATURE,
        ge=0.0,
        le=2.0,
        description="生成温度，0.0=确定性，2.0=创造性",
        examples=[0.3],
    )
    max_tokens: int = Field(
        default=DEFAULT_MAX_TOKENS,
        ge=1,
        le=8000,
        description="生成回答的最大token数",
        examples=[2000],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "什么是RAG技术？它解决了什么问题？",
                "top_k": 5,
                "similarity_threshold": 0.7,
                "use_mmr": False,
                "mmr_lambda": 0.5,
                "metadata_filter": {"file_type": "pdf"},
                "provider": None,
                "temperature": 0.3,
                "max_tokens": 2000,
            }
        },
    )


class RetrievalRequest(BaseModel):
    """检索请求"""

    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="查询内容",
    )
    top_k: int = Field(
        default=DEFAULT_TOP_K,
        ge=1,
        le=20,
        description="返回文档数量",
    )
    similarity_threshold: float = Field(
        default=DEFAULT_SIMILARITY_THRESHOLD,
        ge=0.0,
        le=1.0,
        description="相似度阈值",
    )
    use_mmr: bool = Field(
        default=False,
        description="是否使用MMR算法",
    )
    mmr_lambda: float = Field(
        default=DEFAULT_MMR_LAMBDA,
        ge=0.0,
        le=1.0,
        description="MMR lambda参数",
    )
    metadata_filter: dict[str, Any] | None = Field(
        default=None,
        description="元数据过滤条件",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "RAG是什么",
                "top_k": 5,
                "similarity_threshold": 0.7,
            }
        },
    )


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


RetrievedDocument = RetrievedChunk
"""检索命中片段（领域契约别名；单一事实来源 qingchuan_domain.schemas.retrieval.RetrievedChunk）。

保留本别名保证 rag 既有导入路径不变；HTTP 与 MCP 响应均序列化为领域契约结构。
"""


def from_search_results(results: list[dict[str, Any]]) -> list[RetrievedDocument]:
    """将检索服务返回的原始结果转换为领域契约片段列表（HTTP 与 MCP 层共用）。

    混合检索（向量 + BM25）产出的 score 量纲不一致：向量相似度 ∈ [0,1]，
    BM25 原始分数无上界；领域契约约束 score ∈ [0,1]，这里统一收敛。
    """
    return [
        RetrievedDocument(
            chunk_id=doc["id"],
            document_id=doc["metadata"].get("document_id", ""),
            text=doc["text"],
            score=max(0.0, min(1.0, float(doc.get("score", 0.0)))),
            metadata=doc["metadata"],
        )
        for doc in results
    ]


class RAGQueryResponse(BaseModel):
    """RAG查询响应"""

    query: str = Field(..., description="查询内容")
    answer: str = Field(..., description="生成的答案")
    retrieved_docs: list[RetrievedDocument] = Field(
        ...,
        description="检索到的文档",
    )
    provider: str = Field(..., description="使用的LLM提供商")
    model: str = Field(..., description="使用的模型")
    tokens_used: int | None = Field(
        default=None,
        description="使用的token数",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "什么是RAG？",
                "answer": "RAG是检索增强生成...",
                "retrieved_docs": [],
                "provider": "mimo",
                "model": "mimo-v2.6-pro",
                "tokens_used": 500,
            }
        },
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


class RetrievalResponse(BaseModel):
    """检索响应"""

    query: str = Field(..., description="查询内容")
    documents: list[RetrievedDocument] = Field(..., description="检索到的文档")
    total: int = Field(..., description="检索到的文档总数")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "RAG是什么",
                "documents": [],
                "total": 5,
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
