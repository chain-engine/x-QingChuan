#!/usr/bin/env python3
"""检索端口适配器：将 rag-service 三阶段检索流水线适配为共享领域协议 RetrievalPort。

共享领域包 qingchuan_domain 定义 RetrievalPort / RetrievalQuery /
RetrievalResponse 契约；本适配器在 rag-service 内把三阶段检索
流水线（向量 / BM25 候选 → RRF 融合 → 阈值 / MMR 重排）包装为领域协议，
供未来 agent-service 以库方式集成时直接依赖端口，不感知向量库实现。
"""

from __future__ import annotations

from qingchuan_domain.constants.retrieval import DEFAULT_SIMILARITY_THRESHOLD
from qingchuan_domain.ports.retrieval import RetrievalPort
from qingchuan_domain.schemas.retrieval import (
    RetrievalQuery,
    RetrievalResponse,
    RetrievedChunk,
)
from qingchuan_rag.services.rag_service import RAGService


class RetrievalAdapter(RetrievalPort):
    """RetrievalPort 的 rag-service 实现（内部复用 RAGService 检索流水线）。"""

    def __init__(self, rag_service: RAGService) -> None:
        self._rag_service = rag_service

    async def retrieve(self, query: RetrievalQuery) -> RetrievalResponse:
        """按领域协议执行检索并转换为 RetrievalResponse。"""
        results = self._rag_service.retrieve(
            query=query.query,
            top_k=query.top_k,
            similarity_threshold=(
                query.similarity_threshold
                if query.similarity_threshold is not None
                else DEFAULT_SIMILARITY_THRESHOLD
            ),
            use_mmr=query.use_mmr,
            mmr_lambda=query.mmr_lambda,
            metadata_filter=query.metadata_filter,
        )
        chunks = [
            RetrievedChunk(
                chunk_id=item["id"],
                document_id=item.get("metadata", {}).get("document_id", ""),
                source=item.get("metadata", {}).get("source_type", ""),
                text=item.get("text", ""),
                score=item.get("score", 0.0),
                metadata=item.get("metadata", {}),
            )
            for item in results
        ]
        return RetrievalResponse(
            query=query.query,
            chunks=chunks,
            total=len(chunks),
        )


__all__ = ["RetrievalAdapter"]
