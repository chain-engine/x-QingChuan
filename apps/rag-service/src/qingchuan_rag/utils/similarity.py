"""
Similarity Search Engine Module

相似度搜索算法工具类

— 封装多种向量距离和相似度计算算法
"""

import numpy as np

from qingchuan_rag.constants import (
    DistanceType,
)
from qingchuan_rag.core.exceptions import RetrievalError


class SimilaritySearchEngine:
    """
    向量相似度搜索引擎

    支持多种距离度量方式，用于计算查询向量与文档向量之间的相似度。

    使用方式：
        engine = SimilaritySearchEngine(distance_type=DistanceType.COSINE)
        score = engine.compute(query_vector, doc_vector)
        scores = engine.compute_batch(query_vector, doc_vectors)
    """

    def __init__(
        self,
        distance_type: DistanceType = DistanceType.COSINE,
    ):
        """
        初始化相似度搜索引擎

        Args:
            distance_type: 默认的距离度量类型
        """
        self._distance_type = distance_type

    @property
    def distance_type(self) -> DistanceType:
        """获取当前使用的距离类型"""
        return self._distance_type

    def set_distance_type(self, distance_type: DistanceType) -> None:
        """设置距离类型"""
        self._distance_type = distance_type

    def compute(
        self,
        query_vector: list[float],
        doc_vector: list[float],
        distance_type: DistanceType | None = None,
    ) -> float:
        """
        计算单个相似度

        Args:
            query_vector: 查询向量
            doc_vector: 文档向量
            distance_type: 距离度量类型（可选，默认使用实例的 distance_type）

        Returns:
            float: 相似度分数
        """
        dtype = distance_type or self._distance_type
        return self._compute_impl(query_vector, doc_vector, dtype)

    def compute_batch(
        self,
        query_vector: list[float],
        doc_vectors: list[list[float]],
        distance_type: DistanceType | None = None,
    ) -> list[float]:
        """
        批量计算相似度

        Args:
            query_vector: 查询向量
            doc_vectors: 文档向量列表
            distance_type: 距离度量类型（可选）

        Returns:
            List[float]: 相似度分数列表
        """
        dtype = distance_type or self._distance_type
        return self._compute_batch_impl(query_vector, doc_vectors, dtype)

    # === 内部实现 ===

    def _compute_impl(
        self,
        query_vector: list[float],
        doc_vector: list[float],
        distance_type: DistanceType,
    ) -> float:
        """内部实现：单条相似度计算"""
        query = np.array(query_vector)
        doc = np.array(doc_vector)

        if distance_type == DistanceType.COSINE:
            norm_query = np.linalg.norm(query)
            norm_doc = np.linalg.norm(doc)
            if norm_query == 0 or norm_doc == 0:
                return 0.0
            return float(np.dot(query, doc) / (norm_query * norm_doc))
        elif distance_type == DistanceType.EUCLIDEAN:
            return float(1.0 / (1.0 + np.linalg.norm(query - doc)))
        elif distance_type == DistanceType.DOT:
            return float(np.dot(query, doc))
        else:
            raise RetrievalError(f"Unsupported distance type: {distance_type}")

    def _compute_batch_impl(
        self,
        query_vector: list[float],
        doc_vectors: list[list[float]],
        distance_type: DistanceType,
    ) -> list[float]:
        """内部实现：批量相似度计算"""
        if not doc_vectors:
            return []

        query = np.array(query_vector)
        docs = np.array(doc_vectors)

        if distance_type == DistanceType.COSINE:
            norms = np.linalg.norm(docs, axis=1)
            query_norm = np.linalg.norm(query)
            if query_norm == 0:
                return [0.0] * len(docs)
            similarities = np.dot(docs, query) / (norms * query_norm)
            similarities[np.isnan(similarities)] = 0.0
            return similarities.tolist()

        elif distance_type == DistanceType.EUCLIDEAN:
            distances = np.linalg.norm(docs - query, axis=1)
            similarities = 1.0 / (1.0 + distances)
            return similarities.tolist()

        elif distance_type == DistanceType.DOT:
            return np.dot(docs, query).tolist()

        else:
            raise RetrievalError(f"Unsupported distance type: {distance_type}")
