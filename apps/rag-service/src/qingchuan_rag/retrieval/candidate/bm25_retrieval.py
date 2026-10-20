"""
BM25 Retrieval Module

BM25 稀疏检索召回

— 基于倒排索引的关键词召回
"""

from typing import Any

from qingchuan_rag.core.logger import logger
from qingchuan_rag.infras.bm25 import BM25IndexStore
from qingchuan_rag.repositories.bm25_repository import BM25Repository
from qingchuan_rag.retrieval.candidate.base import BaseRetrievalProvider


class BM25RetrievalProvider(BaseRetrievalProvider):
    """
    BM25 稀疏检索提供者

    基于 BM25 算法的稀疏检索，适用于关键词精确匹配。
    与向量检索互补，实现多路召回。
    """

    name = "bm25_retrieval"
    description = "BM25 稀疏检索 — 基于倒排索引的关键词召回"

    def __init__(
        self,
        bm25_repo: BM25Repository | None = None,
        persist_directory: str = "./data/bm25",
        index_name: str = "default",
        k1: float = 1.5,
        b: float = 0.75,
        top_k: int = 10,
    ):
        """
        初始化 BM25 检索

        Args:
            bm25_repo: BM25 仓库实例（可选）
            persist_directory: 持久化目录
            index_name: 索引名称
            k1: BM25 k1 参数
            b: BM25 b 参数
            top_k: 默认召回数量
        """
        self._bm25_repo = bm25_repo
        self._persist_directory = persist_directory
        self._index_name = index_name
        self._k1 = k1
        self._b = b
        self._default_top_k = top_k
        self._initialized = False

    @property
    def vector_store(self) -> Any:
        """BM25 不使用向量存储"""
        return None

    @property
    def embedding_model(self) -> Any:
        """BM25 不使用 embedding 模型"""
        return None

    @property
    def bm25_store(self) -> BM25IndexStore:
        """获取 BM25 存储"""
        if self._bm25_repo:
            return self._bm25_repo._store
        raise RuntimeError("BM25 repository not initialized")

    def initialize(self) -> None:
        """初始化 BM25 存储"""
        if self._initialized:
            return

        if self._bm25_repo is None:
            self._bm25_repo = BM25Repository(
                persist_directory=self._persist_directory,
                index_name=self._index_name,
            )
        self._bm25_repo.initialize()

        self._initialized = True
        logger.info(f"BM25RetrievalProvider initialized: index={self._index_name}")

    def shutdown(self) -> None:
        """关闭资源"""
        if self._initialized:
            if self._bm25_repo:
                self._bm25_repo.shutdown()
            self._initialized = False
            logger.info("BM25RetrievalProvider shut down")

    def search(
        self,
        query: str,
        top_k: int = 10,
        metadata_filter: dict[str, Any] | None = None,
        **kwargs,
    ) -> list[dict[str, Any]]:
        """
        执行 BM25 检索

        Args:
            query: 查询文本
            top_k: 返回结果数量
            metadata_filter: 元数据过滤条件
            **kwargs: 额外参数

        Returns:
            list[dict[str, Any]]: 检索结果
        """
        self.initialize()

        results = self._bm25_repo.search(
            query=query,
            top_k=top_k,
            metadata_filter=metadata_filter,
        )

        formatted = []
        for r in results:
            formatted.append(
                {
                    "id": r.get("id"),
                    "text": r.get("text", ""),
                    "score": r.get("score", 0.0),
                    "metadata": r.get("metadata", {}),
                }
            )

        logger.debug(f"BM25RetrievalProvider: found {len(formatted)} results")
        return formatted

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        if not self._initialized:
            return {"type": "bm25", "initialized": False}
        return self._bm25_repo.get_stats()
