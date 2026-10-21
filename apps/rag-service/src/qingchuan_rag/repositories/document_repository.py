#!/usr/bin/env python3
"""
Document Repository Module

Document repository
"""

from typing import Any

from qingchuan_rag.core.logger import logger
from qingchuan_rag.infras.storage import JSONDocumentStore
from qingchuan_rag.repositories.base_repository import BaseRepository


class DocumentRepository(BaseRepository):
    """文档仓库"""

    def __init__(self, storage_path: str = "./data/documents"):
        self._store = JSONDocumentStore(storage_path=storage_path)
        self._initialized = False

    def initialize(self) -> None:
        """初始化文档存储"""
        if self._initialized:
            return
        self._store.initialize()
        self._initialized = True
        logger.info("DocumentRepository initialized")

    def shutdown(self) -> None:
        """关闭文档存储"""
        if self._initialized:
            self._store.shutdown()
            self._initialized = False
            logger.info("DocumentRepository shut down")

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        return self._store.get_stats()

    def save(self, data: dict[str, Any]) -> str:
        """保存文档"""
        self._ensure_initialized()
        document_id = data.get("document_id")
        if not document_id:
            raise ValueError("document_id is required")
        self._store.save(document_id, data)
        return document_id

    def load(self, document_id: str) -> dict[str, Any] | None:
        """加载文档"""
        self._ensure_initialized()
        return self._store.load(document_id)

    def update(self, document_id: str, data: dict[str, Any]) -> None:
        """更新文档"""
        self._ensure_initialized()
        existing = self._store.load(document_id)
        if existing:
            existing.update(data)
            self._store.save(document_id, existing)

    def delete(self, document_id: str) -> None:
        """删除文档"""
        self._ensure_initialized()
        self._store.delete(document_id)

    def list_all(self) -> list[dict[str, Any]]:
        """列出所有文档"""
        self._ensure_initialized()
        return self._store.list_all()

    def list_page(
        self,
        skip: int = 0,
        limit: int | None = None,
        status: str | None = None,
        file_type: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """存储层分页列出文档（过滤与分页下推到存储层）。

        Returns:
            tuple[list[dict[str, Any]], int]: (当前页文档列表, 匹配总数)
        """
        self._ensure_initialized()
        return self._store.list_page(
            skip=skip,
            limit=limit,
            status=status,
            file_type=file_type,
        )

    def exists(self, document_id: str) -> bool:
        """检查文档是否存在"""
        self._ensure_initialized()
        return self._store.load(document_id) is not None

    def _ensure_initialized(self) -> None:
        """确保已初始化"""
        if not self._initialized:
            raise RuntimeError("DocumentRepository not initialized. Call initialize() first.")
