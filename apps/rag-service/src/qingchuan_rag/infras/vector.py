#!/usr/bin/env python3
"""
Vector Store Module

向量存储基础设施：抽象基类 + Chroma 实现。
后续新增向量数据库时，在本模块中扩展新的实现类。
"""

from abc import ABC, abstractmethod
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from qingchuan_rag.core.exceptions import VectorStoreError
from qingchuan_rag.core.logger import logger


class VectorStoreBase(ABC):
    """向量存储基类

    定义向量存储的标准接口
    """

    @abstractmethod
    def initialize(self) -> None:
        """初始化向量存储"""
        pass

    @abstractmethod
    def shutdown(self) -> None:
        """关闭向量存储"""
        pass

    @abstractmethod
    def add(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        """添加向量

        Args:
            ids: 向量ID列表
            embeddings: 向量列表
            documents: 原始文档文本列表
            metadatas: 元数据列表
        """
        pass

    @abstractmethod
    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        where: dict[str, Any] | None = None,
        include: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """搜索相似向量

        Args:
            query_embedding: 查询向量
            top_k: 返回数量
            where: 过滤条件
            include: 返回字段

        Returns:
            list[dict[str, Any]]: 搜索结果列表
        """
        pass

    @abstractmethod
    def delete(self, ids: list[str]) -> None:
        """删除向量

        Args:
            ids: 向量ID列表
        """
        pass

    @abstractmethod
    def get_count(self) -> int:
        """获取向量总数

        Returns:
            int: 向量数量
        """
        pass

    @abstractmethod
    def get_stats(self) -> dict[str, Any]:
        """获取统计信息

        Returns:
            dict[str, Any]: 统计信息
        """
        pass


class ChromaVectorStore(VectorStoreBase):
    """Chroma向量存储实现"""

    DISTANCE_MAP = {
        "cosine": "cosine",
        "euclidean": "l2",
        "dot": "ip",
    }

    def __init__(
        self,
        persist_directory: str = "./data/chroma",
        collection_name: str = "documents",
        distance_type: str = "cosine",
    ):
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self.distance_type = distance_type
        self._client: chromadb.PersistentClient | None = None
        self._collection = None
        self._initialized = False

    def initialize(self) -> None:
        """初始化Chroma客户端和集合"""
        if self._initialized:
            return

        try:
            self._client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=ChromaSettings(
                    anonymized_telemetry=False,
                    allow_reset=True,
                ),
            )

            distance_metric = self.DISTANCE_MAP.get(self.distance_type, "cosine")

            self._collection = self._client.get_or_create_collection(
                name=self.collection_name, metadata={"hnsw:space": distance_metric}
            )

            self._initialized = True
            logger.info(
                f"ChromaVectorStore initialized: collection={self.collection_name}, "
                f"distance={distance_metric}"
            )

        except Exception as e:
            logger.error(f"Failed to initialize ChromaVectorStore: {e}")
            raise VectorStoreError(f"Failed to initialize: {e}") from e

    def shutdown(self) -> None:
        """关闭Chroma客户端"""
        if self._initialized:
            self._client = None
            self._collection = None
            self._initialized = False
            logger.info("ChromaVectorStore shut down")

    def add(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        """添加向量到集合"""
        self._ensure_initialized()

        try:
            self._collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                # Chroma 要求 metadata 为非空 dict，None / 空 dict 都会报错
                metadatas=metadatas or [{"source": "x-qingchuan"} for _ in ids],
            )
            logger.debug(f"Added {len(ids)} vectors to collection")
        except Exception as e:
            logger.error(f"Failed to add vectors: {e}")
            raise VectorStoreError(f"Failed to add vectors: {e}") from e

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        where: dict[str, Any] | None = None,
        include: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """搜索相似向量"""
        self._ensure_initialized()

        if include is None:
            include = ["documents", "metadatas", "distances"]

        try:
            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where,
                include=include,
            )

            if not results or not results.get("ids"):
                return []

            formatted_results = []
            ids_list = results.get("ids", [[]])[0]
            documents_list = results.get("documents", [[]])[0]
            metadatas_list = results.get("metadatas", [[]])[0]
            distances_list = results.get("distances", [[]])[0]

            for i in range(len(ids_list)):
                formatted_results.append(
                    {
                        "id": ids_list[i],
                        "text": documents_list[i] if i < len(documents_list) else "",
                        "metadata": metadatas_list[i] if i < len(metadatas_list) else {},
                        "distance": distances_list[i] if i < len(distances_list) else 0.0,
                    }
                )

            return formatted_results

        except Exception as e:
            logger.error(f"Failed to search vectors: {e}")
            raise VectorStoreError(f"Failed to search: {e}") from e

    def delete(self, ids: list[str]) -> None:
        """删除向量"""
        self._ensure_initialized()

        try:
            self._collection.delete(ids=ids)
            logger.debug(f"Deleted {len(ids)} vectors from collection")
        except Exception as e:
            logger.error(f"Failed to delete vectors: {e}")
            raise VectorStoreError(f"Failed to delete vectors: {e}") from e

    def get_count(self) -> int:
        """获取向量总数"""
        self._ensure_initialized()

        try:
            return self._collection.count()
        except Exception as e:
            logger.error(f"获取向量总数失败: {e}")
            raise VectorStoreError(f"获取向量总数失败: {e}") from e

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        self._ensure_initialized()

        try:
            return {
                "type": "chroma",
                "collection": self.collection_name,
                "count": self._collection.count(),
                "persist_directory": self.persist_directory,
            }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"type": "chroma", "error": str(e)}

    def _ensure_initialized(self) -> None:
        """确保已初始化"""
        if not self._initialized:
            raise VectorStoreError("VectorStore not initialized. Call initialize() first.")


__all__ = [
    "VectorStoreBase",
    "ChromaVectorStore",
]
