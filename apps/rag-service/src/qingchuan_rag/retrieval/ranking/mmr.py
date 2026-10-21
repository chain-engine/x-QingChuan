"""
MMR Reranking Module

MMR — Maximal Marginal Relevance 多样性重排序
"""

from __future__ import annotations

from typing import Any

from qingchuan_rag.core.logger import logger
from qingchuan_rag.infras.embedding import EmbeddingModelBase
from qingchuan_rag.retrieval.ranking.base import BaseRerankingProvider
from qingchuan_rag.utils.similarity import DistanceType, SimilaritySearchEngine


class MMRReranker(BaseRerankingProvider):
    """
    MMR 多样性重排序器

    MMR 通过平衡相关性与多样性来选择文档，避免返回内容高度重复的结果。

    公式：score = λ × relevance - (1 - λ) × max_similarity_to_selected
    - λ 越大：越偏向相关性
    - λ 越小：越偏向多样性
    """

    name: str = "mmr_reranker"
    description: str = "MMR 多样性重排序 — 平衡相关性与多样性"

    def __init__(
        self,
        distance_type: DistanceType = DistanceType.COSINE,
    ) -> None:
        """
        初始化 MMR 重排序器

        Args:
            distance_type: 距离度量类型
        """
        self._distance_type = distance_type
        self._similarity_engine = SimilaritySearchEngine(distance_type=distance_type)

    def rerank(
        self,
        query: str | list[float],
        candidates: list[dict[str, Any]],
        lambda_param: float = 0.5,
        top_k: int | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """
        使用 MMR 算法重排序文档

        Args:
            query: 查询文本或查询向量（如果为文本，需要通过 embedding_model 获取向量）
            candidates: 候选文档列表
            lambda_param: 相关性-多样性权衡参数（0-1）
            top_k: 返回结果数量（可选）
            **kwargs: embedding_model 可通过 kwargs 传入

        Returns:
            list[dict[str, Any]]: MMR 重排序后的文档列表
        """
        if not candidates:
            return []

        if len(candidates) == 1:
            return candidates[:top_k] if top_k else candidates

        query_vector = self._resolve_query_vector(query, candidates, kwargs)
        if query_vector is None:
            logger.warning("MMRReranker: cannot resolve query vector, returning original order")
            return candidates[:top_k] if top_k else candidates

        doc_vectors = []
        for doc in candidates:
            vec = doc.get("embedding") or doc.get("vector")
            if vec is None:
                embedding_model: EmbeddingModelBase | None = kwargs.get("embedding_model")
                if embedding_model:
                    vec = embedding_model.encode_single(doc.get("text", ""))
                else:
                    vec = []
            doc_vectors.append(vec)

        similarities = self._similarity_engine.compute_batch(query_vector, doc_vectors)

        selected_indices: list[int] = []
        remaining_indices = list(range(len(candidates)))

        while remaining_indices:
            mmr_scores: list[tuple[int, float]] = []

            for idx in remaining_indices:
                relevance = similarities[idx]

                max_sim = -1.0
                for selected_idx in selected_indices:
                    sim = self._similarity_engine.compute(
                        doc_vectors[idx],
                        doc_vectors[selected_idx],
                    )
                    if sim > max_sim:
                        max_sim = sim

                mmr_score = lambda_param * relevance - (1 - lambda_param) * max_sim
                mmr_scores.append((idx, mmr_score))

            mmr_scores.sort(key=lambda x: x[1], reverse=True)
            best_idx, _ = mmr_scores[0]

            selected_indices.append(best_idx)
            remaining_indices.remove(best_idx)

            if top_k and len(selected_indices) >= top_k:
                break

        reranked = [candidates[i] for i in selected_indices]
        logger.debug(f"MMRReranker: reranked {len(candidates)} candidates (lambda={lambda_param})")
        return reranked

    def _resolve_query_vector(
        self,
        query: str | list[float],
        candidates: list[dict[str, Any]],
        kwargs: dict[str, Any],
    ) -> list[float] | None:
        """解析查询向量"""
        if isinstance(query, list) and len(query) > 0:
            if isinstance(query[0], (int, float)):
                return query

        embedding_model: EmbeddingModelBase | None = kwargs.get("embedding_model")
        if embedding_model is None:
            return None

        try:
            return embedding_model.encode_single(query)
        except Exception:
            return None
