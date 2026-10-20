#!/usr/bin/env python3
"""
相似度计算单元测试

覆盖当前 utils.similarity.SimilaritySearchEngine：
compute / compute_batch / 距离类型切换 / 边界（零向量、空列表、非法类型）。
（旧 SimilarityCalculator / MetadataFilter / MMRReranker 已在重构中移除）
"""

import pytest

from qingchuan_rag.constants import DistanceType
from qingchuan_rag.core.exceptions import RetrievalError
from qingchuan_rag.utils.similarity import SimilaritySearchEngine


class TestSimilaritySearchEngine:
    """相似度搜索引擎测试"""

    def test_cosine_similarity_same_direction(self):
        engine = SimilaritySearchEngine(DistanceType.COSINE)
        score = engine.compute([1, 2, 3], [2, 4, 6])  # 同向
        assert score == pytest.approx(1.0, abs=0.01)

    def test_cosine_similarity_orthogonal(self):
        engine = SimilaritySearchEngine(DistanceType.COSINE)
        score = engine.compute([1, 0, 0], [0, 1, 0])
        assert score == pytest.approx(0.0, abs=0.01)

    def test_euclidean_similarity(self):
        engine = SimilaritySearchEngine(DistanceType.EUCLIDEAN)
        # 欧氏距离 5 → 相似度 1/(1+5) ≈ 0.1667
        score = engine.compute([0, 0, 0], [3, 4, 0])
        assert score == pytest.approx(1.0 / 6.0, abs=0.01)

    def test_dot_product(self):
        engine = SimilaritySearchEngine(DistanceType.DOT)
        score = engine.compute([1, 2, 3], [4, 5, 6])
        assert score == pytest.approx(32.0)  # 1*4 + 2*5 + 3*6

    def test_zero_vector_returns_zero(self):
        engine = SimilaritySearchEngine(DistanceType.COSINE)
        assert engine.compute([0, 0, 0], [1, 0, 0]) == 0.0
        assert engine.compute([1, 0, 0], [0, 0, 0]) == 0.0

    def test_compute_batch(self):
        engine = SimilaritySearchEngine(DistanceType.COSINE)
        query = [1, 2, 3]
        docs = [[1, 2, 3], [2, 4, 6], [3, 2, 1]]
        scores = engine.compute_batch(query, docs)
        assert len(scores) == 3
        assert scores[0] == pytest.approx(1.0, abs=0.01)
        assert scores[1] == pytest.approx(1.0, abs=0.01)

    def test_compute_batch_empty(self):
        engine = SimilaritySearchEngine(DistanceType.COSINE)
        assert engine.compute_batch([1, 0, 0], []) == []

    def test_set_distance_type(self):
        engine = SimilaritySearchEngine(DistanceType.COSINE)
        engine.set_distance_type(DistanceType.DOT)
        assert engine.distance_type == DistanceType.DOT
        assert engine.compute([1, 1], [1, 1]) == pytest.approx(2.0)

    def test_compute_with_override_distance(self):
        engine = SimilaritySearchEngine(DistanceType.COSINE)
        # 覆盖为 DOT 计算
        score = engine.compute([1, 1], [1, 1], distance_type=DistanceType.DOT)
        assert score == pytest.approx(2.0)

    def test_unsupported_distance(self):
        engine = SimilaritySearchEngine(DistanceType.COSINE)
        with pytest.raises(RetrievalError):
            engine._compute_impl([1, 0], [1, 0], "unsupported")  # type: ignore[arg-type]

    def test_distance_enum_members(self):
        assert DistanceType.COSINE.value == "cosine"
        assert DistanceType.EUCLIDEAN.value == "euclidean"
        assert DistanceType.DOT.value == "dot"
