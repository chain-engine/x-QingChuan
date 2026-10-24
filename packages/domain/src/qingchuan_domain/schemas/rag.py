"""共享领域协议层：RAG 问答请求 / 响应的数据契约（跨服务单一事实来源）。

rag-service 的 HTTP / MCP 接入层与 agent-service 的 MCP 消费侧共用本契约：
    - RAGQueryRequest    问答入参（检索 + 生成参数）
    - RAGQueryResponse   问答结果（答案 + 引用片段，片段复用 RetrievedChunk）
    - from_search_results  原始检索结果 → 领域契约片段（HTTP / MCP 层共用）
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from qingchuan_domain.constants.retrieval import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_MMR_LAMBDA,
    DEFAULT_SIMILARITY_THRESHOLD,
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_K,
)
from qingchuan_domain.schemas.retrieval import RetrievedChunk


class RAGQueryRequest(BaseModel):
    """RAG 问答请求（检索 → 增强 → 生成流水线入参）。"""

    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="用户查询内容，支持中英文",
    )
    top_k: int = Field(
        default=DEFAULT_TOP_K,
        ge=1,
        le=20,
        description="返回相关文档数量",
    )
    similarity_threshold: float = Field(
        default=DEFAULT_SIMILARITY_THRESHOLD,
        ge=0.0,
        le=1.0,
        description="相似度阈值，低于该值的文档被过滤",
    )
    use_mmr: bool = Field(
        default=False,
        description="是否使用 MMR 算法增加结果多样性",
    )
    mmr_lambda: float = Field(
        default=DEFAULT_MMR_LAMBDA,
        ge=0.0,
        le=1.0,
        description="MMR 参数，0.0=多样性优先，1.0=相关性优先",
    )
    metadata_filter: dict[str, Any] | None = Field(
        default=None,
        description="元数据过滤条件，如 {'file_type': 'pdf'}",
    )
    provider: str | None = Field(
        default=None,
        description="LLM 提供商，为空使用默认",
    )
    temperature: float = Field(
        default=DEFAULT_TEMPERATURE,
        ge=0.0,
        le=2.0,
        description="生成温度，0.0=确定性，2.0=创造性",
    )
    max_tokens: int = Field(
        default=DEFAULT_MAX_TOKENS,
        ge=1,
        le=8000,
        description="生成回答的最大 token 数",
    )

    model_config = ConfigDict(json_schema_extra={"example": {
        "query": "什么是 RAG 技术？它解决了什么问题？",
        "top_k": 5,
        "similarity_threshold": 0.7,
        "use_mmr": False,
        "mmr_lambda": 0.5,
        "metadata_filter": {"file_type": "pdf"},
        "provider": None,
        "temperature": 0.3,
        "max_tokens": 2000,
    }})


class RAGQueryResponse(BaseModel):
    """RAG 问答响应（答案 + 引用片段，片段为领域契约 RetrievedChunk）。"""

    query: str = Field(description="原始查询内容")
    answer: str = Field(description="生成的答案")
    retrieved_docs: list[RetrievedChunk] = Field(
        description="检索引用的文档片段列表",
    )
    provider: str = Field(description="使用的 LLM 提供商")
    model: str = Field(description="使用的模型")
    tokens_used: int | None = Field(default=None, description="使用的 token 数")

    model_config = ConfigDict(json_schema_extra={"example": {
        "query": "什么是 RAG？",
        "answer": "RAG 是检索增强生成...",
        "retrieved_docs": [],
        "provider": "mimo",
        "model": "mimo-v2.6-pro",
        "tokens_used": 500,
    }})


def from_search_results(results: list[dict[str, Any]]) -> list[RetrievedChunk]:
    """将检索服务返回的原始结果转换为领域契约片段列表（HTTP 与 MCP 层共用）。

    混合检索（向量 + BM25）产出的 score 量纲不一致：向量相似度 ∈ [0,1]，
    BM25 原始分数无上界；领域契约约束 score ∈ [0,1]，这里统一收敛。
    """
    return [
        RetrievedChunk(
            chunk_id=doc["id"],
            document_id=doc["metadata"].get("document_id", ""),
            text=doc["text"],
            score=max(0.0, min(1.0, float(doc.get("score", 0.0)))),
            metadata=doc["metadata"],
        )
        for doc in results
    ]


__all__ = ["RAGQueryRequest", "RAGQueryResponse", "from_search_results"]
