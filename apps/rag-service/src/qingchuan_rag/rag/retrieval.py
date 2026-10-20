"""
Retrieval Module

检索模块 — 向量检索和重排序（委托至 RetrievalPipeline）
"""

from typing import Any

from qingchuan_rag.core.logger import logger
from qingchuan_rag.infras.embedding import BGEEmbeddingModel
from qingchuan_rag.repositories.bm25_repository import BM25Repository
from qingchuan_rag.repositories.vector_repository import VectorRepository
from qingchuan_rag.retrieval.candidate.bm25_retrieval import BM25RetrievalProvider
from qingchuan_rag.retrieval.candidate.vector_retrieval import ChromaVectorRetrieval
from qingchuan_rag.retrieval.pipeline import RetrievalPipeline
from qingchuan_rag.retrieval.ranking.mmr import MMRReranker
from qingchuan_rag.retrieval.ranking.rrf import RRFReranker
from qingchuan_rag.retrieval.ranking.score_filter import ScoreFilter
from qingchuan_rag.retrieval.understanding.entity import EntityExtractor
from qingchuan_rag.retrieval.understanding.expansion import SynonymExpander
from qingchuan_rag.retrieval.understanding.intent import IntentClassifier
from qingchuan_rag.retrieval.understanding.preprocess import QueryPreprocessor
from qingchuan_rag.retrieval.understanding.rewrite import SimpleQueryRewriter
from qingchuan_rag.utils.similarity import DistanceType, SimilaritySearchEngine


class Retrieval:
    """
    检索器

    本类作为上层 API 入口，委托至 RetrievalPipeline 执行三阶段检索流水线：
    Stage 1 查询理解 → Stage 2 候选召回 → Stage 3 排序筛选
    （增强由 RAGPipeline 的 Augmentation 组件独立完成）

    支持多路召回：
    - 稠密向量检索 (Chroma ANN)
    - 稀疏 BM25 检索 (倒排索引)

    支持重排序：
    - RRF (Reciprocal Rank Fusion) 倒数排名融合 — 融合多路召回结果
    - MMR (Maximum Marginal Relevance) 多样性重排 — 提升结果覆盖率

    """

    def __init__(
        self,
        vector_repo: VectorRepository | None = None,
        bm25_repo: BM25Repository | None = None,
        embedding_model: BGEEmbeddingModel | None = None,
        default_top_k: int = 5,
        default_threshold: float = 0.7,
    ):
        """
        初始化检索器

        Args:
            vector_repo: 向量仓库实例（可选）
            bm25_repo: BM25 仓库实例（可选，用于稀疏索引召回）
            embedding_model: Embedding 模型实例（可选）
            default_top_k: 默认召回数量
            default_threshold: 默认相似度阈值
        """
        self._vector_repo = vector_repo
        self._bm25_repo = bm25_repo
        self._embedding_model = embedding_model
        self._default_top_k = default_top_k
        self._default_threshold = default_threshold
        self._initialized = False

        # ── 构建检索流水线 ──────────────────────────
        # Stage 1: 查询理解
        understanding_providers = [
            QueryPreprocessor(),  # 预处理
            IntentClassifier(),  # 意图识别
            EntityExtractor(),  # 实体抽取
            SynonymExpander(),  # 同义词扩展
            SimpleQueryRewriter(),  # 简单规则重写
        ]

        # Stage 2: 候选召回 — 多路召回
        candidate_providers = []

        # 稠密向量检索
        vector_retrieval = ChromaVectorRetrieval(
            vector_repo=vector_repo,
            embedding_model=embedding_model,
            top_k=default_top_k,
        )
        candidate_providers.append(vector_retrieval)

        # 稀疏 BM25 检索
        if bm25_repo is not None:
            bm25_retrieval = BM25RetrievalProvider(
                bm25_repo=bm25_repo,
                top_k=default_top_k,
            )
            candidate_providers.append(bm25_retrieval)
            logger.info("Multi-way retrieval enabled: vector + BM25")

        # Stage 3: 排序筛选 — RRF 融合多路召回结果后，再做 MMR 多样性排序
        # 顺序很重要：RRF 先融合 → MMR 后重排（确保多样性的基础上融合）
        reranking_providers = [
            RRFReranker(k=60),  # 融合多路召回（向量 + BM25）的结果
            MMRReranker(distance_type=DistanceType.COSINE),  # 多样性重排
        ]
        filter_providers = [
            ScoreFilter(threshold=default_threshold),
        ]

        self._pipeline = RetrievalPipeline(
            understanding_providers=understanding_providers,
            candidate_providers=candidate_providers,
            reranking_providers=reranking_providers,
            filter_providers=filter_providers,
            similarity_engine=SimilaritySearchEngine(distance_type=DistanceType.COSINE),
            default_top_k=default_top_k,
            default_threshold=default_threshold,
        )

    def initialize(self) -> None:
        """初始化"""
        self._pipeline.initialize()
        self._initialized = True
        logger.info("Retrieval initialized")

    def shutdown(self) -> None:
        """关闭"""
        if self._initialized:
            self._pipeline.shutdown()
            self._initialized = False
            logger.info("Retrieval shut down")

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        return self._pipeline.get_stats()

    def encode(self, texts: list[str], normalize: bool = True) -> list[list[float]]:
        """将文本转换为向量"""
        self._check_initialized()
        if self._embedding_model:
            return self._embedding_model.encode(texts, normalize=normalize)
        return []

    def get_embedding_stats(self) -> dict[str, Any]:
        """获取嵌入模型统计信息"""
        if self._embedding_model:
            return {
                "model": self._embedding_model.model_name,
                "dimension": self._embedding_model.dimension,
            }
        return {"model": "unknown", "dimension": 0}

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        similarity_threshold: float = 0.7,
        use_mmr: bool = False,
        mmr_lambda: float = 0.5,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        检索相关文档

        Args:
            query: 查询文本
            top_k: 召回数量
            similarity_threshold: 相似度阈值
            use_mmr: 是否使用 MMR 多样性排序
            mmr_lambda: MMR 参数
            metadata_filter: 元数据过滤条件

        Returns:
            list[dict[str, Any]]: 检索结果
        """
        self._check_initialized()

        results = self._pipeline.retrieve(
            query=query,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
            metadata_filter=metadata_filter,
            use_mmr=use_mmr,
            mmr_lambda=mmr_lambda,
        )

        formatted = []
        for result in results[:top_k]:
            formatted.append(
                {
                    "id": result.get("id"),
                    "text": result.get("text"),
                    "score": result.get("score", 0),
                    "metadata": result.get("metadata", {}),
                }
            )

        return formatted

    def get_vector_count(self) -> int:
        """获取向量总数"""
        self._check_initialized()
        stats = self._pipeline.get_stats()
        stats_info = stats.get("candidate_stats", {})
        for stat in stats_info.values():
            return stat.get("count", 0)
        return 0

    def _check_initialized(self) -> None:
        """检查是否已初始化"""
        if not self._initialized:
            raise RuntimeError("Retrieval not initialized. Call initialize() first.")
