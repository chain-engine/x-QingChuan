"""共享领域协议层：RAG 检索端口（实现侧不可侵入领域）。

下游（agent-service / API 层）只依赖 RetrievalPort 契约，
不感知向量库（Chroma）与检索管道的具体实现。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from qingchuan_domain.schemas.retrieval import RetrievalQuery, RetrievalResponse


@runtime_checkable
class RetrievalPort(Protocol):
    """语义检索契约：按查询返回知识库中最相关的片段。"""

    async def retrieve(self, query: RetrievalQuery) -> RetrievalResponse:
        """按语义相关性返回检索片段。

        TODO: 由 rag-service 内的 RetrievalAdapter 实现（内部复用 rag-service
        三阶段检索流水线：向量 / BM25 候选 → RRF 融合 → 阈值 / MMR 重排）。
        """
        ...


__all__ = ["RetrievalPort"]
