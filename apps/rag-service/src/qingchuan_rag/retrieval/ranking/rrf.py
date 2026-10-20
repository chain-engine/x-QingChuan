"""
RRF Reranking Module

RRF — Reciprocal Rank Fusion 倒数排名融合
"""

from __future__ import annotations

from typing import Any

from qingchuan_rag.core.logger import logger
from qingchuan_rag.retrieval.ranking.base import BaseRerankingProvider


class RRFReranker(BaseRerankingProvider):
    """
    RRF 倒数排名融合器

    通过多路检索结果的倒数排名进行融合，适用于集成多种检索方法的结果。
    """

    name: str = "rrf_reranker"
    description: str = "RRF 倒数排名融合 — 融合多路检索结果"

    def __init__(self, k: int = 60) -> None:
        """
        初始化 RRF 融合器

        Args:
            k: RRF 公式中的常数（通常为 60），k 值越大，不同排名列表间的差异越小
        """
        self._k = k

    def rerank(
        self,
        query: str | list[float],
        candidates: list[dict[str, Any]],
        ranked_lists: list[list[dict[str, Any]]] | None = None,
        top_k: int | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """
        使用 RRF 算法融合多个排名列表

        Args:
            query: 查询（此方法不使用，仅满足接口）
            candidates: 默认候选列表（未使用时传入）
            ranked_lists: 多路检索结果列表
            top_k: 返回结果数量
            **kwargs: 额外参数

        Returns:
            list[dict[str, Any]]: RRF 融合后的文档列表
        """
        if ranked_lists is None or len(ranked_lists) == 0:
            logger.warning("RRFReranker: no ranked lists provided, returning candidates as-is")
            return candidates[:top_k] if top_k else candidates

        rrf_scores: dict[str, float] = {}
        doc_map: dict[str, dict[str, Any]] = {}

        for ranked_list in ranked_lists:
            for rank, doc in enumerate(ranked_list):
                doc_id = doc.get("id")
                if doc_id is None:
                    continue

                if doc_id not in rrf_scores:
                    rrf_scores[doc_id] = 0.0
                    doc_map[doc_id] = doc

                rrf_scores[doc_id] += 1.0 / (self._k + rank + 1)

        sorted_docs = sorted(
            rrf_scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        result = [doc_map[doc_id] for doc_id, _ in sorted_docs]
        logger.debug(f"RRFReranker: fused {len(ranked_lists)} lists into {len(result)} docs")

        return result[:top_k] if top_k else result
