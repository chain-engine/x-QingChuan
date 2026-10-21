#!/usr/bin/env python3
"""
BM25 Repository Module

BM25 稀疏索引仓库 — 管理倒排索引的生命周期
"""

from typing import Any

from qingchuan_rag.core.logger import logger
from qingchuan_rag.infras.bm25 import BM25IndexStore
from qingchuan_rag.repositories.base_repository import BaseRepository


class BM25Repository(BaseRepository):
    """
    BM25 仓库

    封装 BM25IndexStore，提供持久化和生命周期管理。
    """

    def __init__(
        self,
        persist_directory: str = "./data/bm25",
        index_name: str = "default",
        k1: float = 1.5,
        b: float = 0.75,
    ):
        self._store = BM25IndexStore(
            persist_directory=persist_directory,
            index_name=index_name,
            k1=k1,
            b=b,
        )
        self._initialized = False

    def initialize(self) -> None:
        """初始化 BM25 存储"""
        if self._initialized:
            return
        self._store.initialize()
        self._initialized = True
        logger.info("BM25Repository initialized")

    def shutdown(self) -> None:
        """关闭 BM25 存储"""
        if self._initialized:
            self._store.shutdown()
            self._initialized = False
            logger.info("BM25Repository shut down")

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        return self._store.get_stats()

    def add(
        self,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        """
        添加文档到 BM25 索引

        Args:
            ids: 文档ID列表
            documents: 文档文本列表
            metadatas: 元数据列表
        """
        self._ensure_initialized()
        self._store.add(ids, documents, metadatas)

    def search(
        self,
        query: str,
        top_k: int = 5,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        搜索 BM25 索引

        Args:
            query: 查询文本
            top_k: 返回数量
            metadata_filter: 元数据过滤条件

        Returns:
            搜索结果列表
        """
        self._ensure_initialized()
        return self._store.search(query, top_k, metadata_filter)

    def delete(self, ids: list[str]) -> None:
        """删除文档"""
        self._ensure_initialized()
        self._store.delete(ids)

    def delete_by_document_id(self, document_id: str) -> int:
        """根据文档ID删除该文档的全部 chunks。"""
        self._ensure_initialized()

        ids_to_delete = [
            r["id"]
            for r in self._store.get_all()
            if r.get("metadata", {}).get("document_id") == document_id
        ]

        if ids_to_delete:
            self._store.delete(ids_to_delete)

        return len(ids_to_delete)

    def get_by_document_id(self, document_id: str) -> list[dict[str, Any]]:
        """根据文档ID获取 chunks。"""
        self._ensure_initialized()

        return [
            r
            for r in self._store.get_all()
            if r.get("metadata", {}).get("document_id") == document_id
        ]

    def get_count(self) -> int:
        """获取文档数量"""
        self._ensure_initialized()
        return self._store.get_count()

    def _ensure_initialized(self) -> None:
        """确保已初始化"""
        if not self._initialized:
            raise RuntimeError("BM25Repository not initialized. Call initialize() first.")
