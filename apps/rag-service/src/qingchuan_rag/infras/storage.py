#!/usr/bin/env python3
"""
Storage Module

文档存储基础设施：抽象基类 + JSON 文件实现
"""

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from qingchuan_rag.core.exceptions import DocumentError
from qingchuan_rag.core.logger import logger
from qingchuan_rag.core.paths import resolve_service_path


class DocumentStoreBase(ABC):
    """文档存储基类

    定义文档存储的标准接口
    """

    @abstractmethod
    def initialize(self) -> None:
        """初始化文档存储"""
        pass

    @abstractmethod
    def shutdown(self) -> None:
        """关闭文档存储"""
        pass

    @abstractmethod
    def save(self, document_id: str, data: dict[str, Any]) -> None:
        """保存文档

        Args:
            document_id: 文档ID
            data: 文档数据
        """
        pass

    @abstractmethod
    def load(self, document_id: str) -> dict[str, Any] | None:
        """加载文档

        Args:
            document_id: 文档ID

        Returns:
            dict[str, Any] | None: 文档数据
        """
        pass

    @abstractmethod
    def delete(self, document_id: str) -> None:
        """删除文档

        Args:
            document_id: 文档ID
        """
        pass

    @abstractmethod
    def list_all(self) -> list[dict[str, Any]]:
        """列出所有文档

        Returns:
            list[dict[str, Any]]: 文档列表
        """
        pass

    @abstractmethod
    def list_page(
        self,
        skip: int = 0,
        limit: int | None = None,
        status: str | None = None,
        file_type: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """存储层分页列出文档（过滤与分页在存储层完成，返回 (页内文档, 匹配总数)）。

        Args:
            skip: 跳过匹配数量
            limit: 返回数量上限（None 表示不限制）
            status: 按状态过滤
            file_type: 按文件类型过滤

        Returns:
            tuple[list[dict[str, Any]], int]: (当前页文档列表, 匹配过滤条件的文档总数)
        """
        pass

    @abstractmethod
    def get_stats(self) -> dict[str, Any]:
        """获取统计信息

        Returns:
            dict[str, Any]: 统计信息
        """
        pass


class JSONDocumentStore(DocumentStoreBase):
    """JSON文件文档存储实现"""

    def __init__(self, storage_path: str = "./data/documents"):
        # 相对路径锚定到服务根目录（apps/rag-service/data），避免随 CWD 漂移写入仓库根目录
        self.storage_path = Path(resolve_service_path(storage_path))
        self._initialized = False

    def initialize(self) -> None:
        """初始化存储目录"""
        if self._initialized:
            return

        try:
            self.storage_path.mkdir(parents=True, exist_ok=True)
            self._initialized = True
            logger.info(f"JSONDocumentStore initialized: path={self.storage_path}")
        except Exception as e:
            logger.error(f"Failed to initialize JSONDocumentStore: {e}")
            raise DocumentError(f"Failed to initialize: {e}") from e

    def shutdown(self) -> None:
        """关闭存储"""
        self._initialized = False
        logger.info("JSONDocumentStore shut down")

    def _get_file_path(self, document_id: str) -> Path:
        """获取文档文件路径"""
        return self.storage_path / f"{document_id}.json"

    def save(self, document_id: str, data: dict[str, Any]) -> None:
        """保存文档到JSON文件"""
        self._ensure_initialized()

        try:
            file_path = self._get_file_path(document_id)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug(f"Saved document: {document_id}")
        except Exception as e:
            logger.error(f"Failed to save document {document_id}: {e}")
            raise DocumentError(f"Failed to save document: {e}") from e

    def load(self, document_id: str) -> dict[str, Any] | None:
        """从JSON文件加载文档"""
        self._ensure_initialized()

        try:
            file_path = self._get_file_path(document_id)
            if not file_path.exists():
                return None

            with open(file_path, encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"文档 {document_id} 解析失败：无效的JSON格式: {e}")
            raise DocumentError(f"文档 {document_id} 格式无效: {e}") from e
        except PermissionError as e:
            logger.error(f"读取文档 {document_id} 权限不足: {e}")
            raise DocumentError(f"读取文档 {document_id} 权限不足") from e
        except OSError as e:
            logger.error(f"加载文档 {document_id} 失败: {e}")
            raise DocumentError(f"加载文档 {document_id} 失败: {e}") from e

    def delete(self, document_id: str) -> None:
        """删除文档文件"""
        self._ensure_initialized()

        try:
            file_path = self._get_file_path(document_id)
            if file_path.exists():
                file_path.unlink()
                logger.debug(f"Deleted document: {document_id}")
        except Exception as e:
            logger.error(f"Failed to delete document {document_id}: {e}")
            raise DocumentError(f"Failed to delete document: {e}") from e

    def list_all(self) -> list[dict[str, Any]]:
        """列出所有文档"""
        self._ensure_initialized()

        documents = []
        failed_files = []
        try:
            for file_path in self.storage_path.glob("*.json"):
                try:
                    with open(file_path, encoding="utf-8") as f:
                        documents.append(json.load(f))
                except json.JSONDecodeError as e:
                    logger.warning(f"跳过无效的JSON文件 {file_path}: {e}")
                    failed_files.append(str(file_path))
                except PermissionError:
                    logger.warning(f"跳过无权限访问的文件 {file_path}")
                    failed_files.append(str(file_path))
                except OSError as e:
                    logger.warning(f"跳过无法读取的文件 {file_path}: {e}")
                    failed_files.append(str(file_path))

            if failed_files:
                logger.warning(f"共跳过 {len(failed_files)} 个不可读文件: {failed_files[:5]}")

            return documents
        except Exception as e:
            logger.error(f"列出文档失败: {e}")
            raise DocumentError(f"列出文档失败: {e}") from e

    def list_page(
        self,
        skip: int = 0,
        limit: int | None = None,
        status: str | None = None,
        file_type: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """存储层分页列出文档（流式遍历 + 仅保留窗口，避免全量加载到内存）。

        JSON 文件存储无法像 SQL 一样在索引层下推过滤/分页，仍需遍历全部文件
        计算匹配总数；但相比"全量加载到内存再切片"，本实现只保留分页窗口内的
        文档，内存占用 O(window) 而非 O(n)，服务层不再持有全量列表。
        """
        self._ensure_initialized()

        matched_count = 0
        page: list[dict[str, Any]] = []
        failed_files: list[str] = []

        try:
            for file_path in self.storage_path.glob("*.json"):
                try:
                    with open(file_path, encoding="utf-8") as f:
                        data = json.load(f)
                except json.JSONDecodeError as e:
                    logger.warning(f"跳过无效的JSON文件 {file_path}: {e}")
                    failed_files.append(str(file_path))
                    continue
                except PermissionError:
                    logger.warning(f"跳过无权限访问的文件 {file_path}")
                    failed_files.append(str(file_path))
                    continue
                except OSError as e:
                    logger.warning(f"跳过无法读取的文件 {file_path}: {e}")
                    failed_files.append(str(file_path))
                    continue

                if status is not None and data.get("status") != status:
                    continue
                if file_type is not None and data.get("file_type") != file_type:
                    continue

                matched_count += 1
                # 只保留分页窗口内的文档，超出窗口仅计数不保留
                if matched_count > skip and (limit is None or len(page) < limit):
                    page.append(data)

            if failed_files:
                logger.warning(f"共跳过 {len(failed_files)} 个不可读文件: {failed_files[:5]}")

            return page, matched_count
        except Exception as e:
            logger.error(f"分页列出文档失败: {e}")
            raise DocumentError(f"列出文档失败: {e}") from e

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        self._ensure_initialized()

        try:
            files = list(self.storage_path.glob("*.json"))
            return {
                "type": "json",
                "storage_path": str(self.storage_path),
                "document_count": len(files),
            }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"type": "json", "error": str(e)}

    def _ensure_initialized(self) -> None:
        """确保已初始化"""
        if not self._initialized:
            raise DocumentError("DocumentStore not initialized. Call initialize() first.")


__all__ = [
    "DocumentStoreBase",
    "JSONDocumentStore",
]
