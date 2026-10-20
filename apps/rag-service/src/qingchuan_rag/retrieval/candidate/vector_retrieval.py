"""
Vector Retrieval Module

向量检索召回

— 基于向量相似度的召回算法
"""

from typing import Any

from qingchuan_rag.core.logger import logger
from qingchuan_rag.infras.embedding import BGEEmbeddingModel
from qingchuan_rag.repositories.vector_repository import VectorRepository
from qingchuan_rag.retrieval.candidate.base import BaseRetrievalProvider


class VectorRetrievalProvider(BaseRetrievalProvider):
    """
    向量检索提供者基类

    基于向量空间中的相似度计算进行文档召回。
    """

    name = "vector_retrieval"
    description = "向量检索 — 基于向量相似度的召回"

    @property
    def vector_store(self) -> Any:
        raise NotImplementedError("子类必须实现 vector_store 属性")

    @property
    def embedding_model(self) -> Any:
        raise NotImplementedError("子类必须实现 embedding_model 属性")

    def search(
        self,
        query: str | list[float],
        top_k: int = 10,
        **kwargs,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError("子类必须实现 search 方法")


class ChromaVectorRetrieval(VectorRetrievalProvider):
    """
    Chroma 向量检索召回

    使用 Chroma 向量数据库进行 ANN 检索，复用现有的 VectorRepository 实现。
    """

    name = "chroma_vector_retrieval"
    description = "Chroma 向量检索召回 — 基于 Chroma 的 ANN 检索"

    def __init__(
        self,
        vector_repo: VectorRepository | None = None,
        embedding_model: BGEEmbeddingModel | None = None,
        persist_directory: str = "./data/chroma",
        collection_name: str = "documents",
        distance_type: str = "cosine",
        top_k: int = 10,
    ):
        """
        初始化 Chroma 向量检索召回

        Args:
            vector_repo: 向量仓库实例（可选）
            embedding_model: Embedding 模型实例（可选）
            persist_directory: Chroma 持久化目录
            collection_name: Collection 名称
            distance_type: 距离类型
            top_k: 默认召回数量
        """
        self._vector_repo = vector_repo
        self._embedding_model = embedding_model
        self._persist_directory = persist_directory
        self._collection_name = collection_name
        self._distance_type = distance_type
        self._default_top_k = top_k
        self._initialized = False

    @property
    def vector_store(self) -> VectorRepository:
        """获取向量仓库"""
        return self._vector_repo

    @property
    def embedding_model(self) -> BGEEmbeddingModel:
        """获取 embedding 模型"""
        return self._embedding_model

    def initialize(self) -> None:
        """初始化向量仓库和 embedding 模型"""
        if self._initialized:
            return

        if self._vector_repo is None:
            self._vector_repo = VectorRepository(
                persist_directory=self._persist_directory,
                collection_name=self._collection_name,
                distance_type=self._distance_type,
            )
        self._vector_repo.initialize()

        if self._embedding_model is None:
            self._embedding_model = BGEEmbeddingModel()

        self._initialized = True
        logger.info(f"ChromaVectorRetrieval initialized: collection={self._collection_name}")

    def shutdown(self) -> None:
        """关闭资源"""
        if self._initialized:
            if self._vector_repo:
                self._vector_repo.shutdown()
            if self._embedding_model:
                self._embedding_model.shutdown()
            self._initialized = False
            logger.info("ChromaVectorRetrieval shut down")

    def search(
        self,
        query: str | list[float],
        top_k: int = 10,
        metadata_filter: dict[str, Any] | None = None,
        **kwargs,
    ) -> list[dict[str, Any]]:
        """
        执行向量检索

        Args:
            query: 查询文本或查询向量
            top_k: 返回结果数量
            metadata_filter: 元数据过滤条件
            **kwargs: 额外参数

        Returns:
            list[dict[str, Any]]: 检索结果
        """
        self.initialize()

        if isinstance(query, str):
            # 文本向量化
            query_embedding = self._embedding_model.encode_single(query, normalize=True)
        else:
            query_embedding = query

        results = self._vector_repo.search(
            query_embedding=query_embedding,
            top_k=top_k,
            where=metadata_filter,
        )

        formatted = []
        for r in results:
            formatted.append(
                {
                    "id": r.get("id"),
                    "text": r.get("document", r.get("text", "")),
                    "score": r.get("score", 0.0),
                    "metadata": r.get("metadata", {}),
                    "embedding": r.get("embedding"),
                }
            )

        logger.debug(f"ChromaVectorRetrieval: found {len(formatted)} results")
        return formatted
