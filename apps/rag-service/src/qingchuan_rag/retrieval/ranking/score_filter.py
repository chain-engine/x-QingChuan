"""
Score Filter Module

分值过滤

— 基于相似度阈值的过滤
"""

from __future__ import annotations

from typing import Any

from qingchuan_rag.core.logger import logger
from qingchuan_rag.retrieval.ranking.base import BaseFilterProvider


class ScoreFilter(BaseFilterProvider):
    """
    分值过滤器

    基于相似度/相关分值阈值过滤低质量候选文档。
    """

    name: str = "score_filter"
    description: str = "分值过滤器 — 基于阈值的文档过滤"

    def __init__(
        self,
        threshold: float = 0.7,
        score_field: str = "score",
    ) -> None:
        """
        初始化分值过滤器

        Args:
            threshold: 过滤阈值，低于此值的文档将被过滤
            score_field: 分数字段名（score / semantic_score / bm25_score 等）
        """
        self._threshold = threshold
        self._score_field = score_field

    def filter(
        self,
        candidates: list[dict[str, Any]],
        threshold: float | None = None,
        top_k: int | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """
        过滤低于阈值的文档

        Args:
            candidates: 候选文档列表
            threshold: 过滤阈值（可选，优先级高于构造函数的 threshold）
            top_k: 返回结果数量（可选）
            **kwargs: 额外参数

        Returns:
            list[dict[str, Any]]: 过滤后的文档列表
        """
        effective_threshold = threshold if threshold is not None else self._threshold
        score_field = kwargs.get("score_field", self._score_field)

        filtered = [doc for doc in candidates if doc.get(score_field, 0.0) >= effective_threshold]

        filtered.sort(key=lambda x: x.get(score_field, 0.0), reverse=True)

        logger.debug(
            f"ScoreFilter: filtered {len(candidates)} -> {len(filtered)} "
            f"(threshold={effective_threshold})"
        )

        return filtered[:top_k] if top_k else filtered
