#!/usr/bin/env python3
"""
Document Repository Module（方案 A：元数据入库 SQLAlchemy 版）

文档【元数据】落业务库（MySQL 生产 / SQLite 本地），文档【内容】
经 infras.storage.py 存储抽象层落对象存储；本仓库面向业务层暴露
与旧 JSON 存储一致的方法接口（save / load / update / delete /
list_page / exists / get_stats），调用方零改动适配。

数据映射规则：已知列字段直接落列；未知字段并入 metadata JSON，
回读时 metadata 原样返回（不展开到顶层）。
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from qingchuan_rag.core.logger import logger
from qingchuan_rag.infras.database import get_cached_database_provider
from qingchuan_rag.infras.storage import StorageProvider, get_cached_storage_provider
from qingchuan_rag.models.document_entity import DocumentEntity
from qingchuan_rag.repositories.base_repository import BaseRepository

# 落列的字段白名单（"metadata" 为对外语义键，映射到实体 extra JSON 列；
# 其余未知字段并入 extra JSON，回读时以 metadata 键原样返回）
_COLUMN_FIELDS: frozenset[str] = frozenset(
    {
        "document_id",
        "file_name",
        "file_type",
        "file_size",
        "status",
        "chunk_count",
        "content_key",
        "storage_backend",
        "content_url",
        "checksum",
    }
)


def _split_fields(data: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """拆分 data 为（列字段 dict, 未知字段 dict, 显式 metadata dict）。"""
    columns: dict[str, Any] = {}
    extra: dict[str, Any] = {}
    metadata: dict[str, Any] = data.get("metadata") or {}
    for key, value in data.items():
        if key in _COLUMN_FIELDS:
            columns[key] = value
        elif key != "metadata":
            extra[key] = value
    return columns, extra, metadata


class DocumentRepository(BaseRepository):
    """文档仓库（SQLAlchemy：documents 表 + 内容对象存储）。"""

    def __init__(
        self,
        storage: StorageProvider | None = None,
        session: Session | None = None,
    ) -> None:
        """构造文档仓库。

        Args:
            storage: 文件存储提供者（文档内容对象存储）；缺省从配置自动创建
            session: 测试注入用会话；缺省每次操作自建独立会话
        """
        self._storage = storage if storage is not None else get_cached_storage_provider()
        self._session = session
        self._initialized = False

    def initialize(self) -> None:
        """初始化文档仓库（存储层基址由 LocalStorage 构造时确保存在）。"""
        if self._initialized:
            return
        self._initialized = True
        logger.info("DocumentRepository initialized (metadata in DB, content in object storage)")

    def shutdown(self) -> None:
        """关闭文档仓库。"""
        if self._initialized:
            self._initialized = False
            logger.info("DocumentRepository shut down")

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息。"""
        self._ensure_initialized()
        with self._db_session() as session:
            document_count = session.scalar(select(func.count(DocumentEntity.id))) or 0
        return {
            "type": "document",
            "storage_backend": self._storage.storage_type,
            "document_count": int(document_count),
        }

    # ── 写操作 ──────────────────────────────────────────────
    def save(self, data: dict[str, Any]) -> str:
        """保存文档元数据（幂等覆盖：同 document_id 已存在则整体更新）。"""
        self._ensure_initialized()
        document_id = data.get("document_id")
        if not document_id:
            raise ValueError("document_id is required")
        columns, extra, metadata = _split_fields(data)
        now = datetime.now(UTC)
        extra_merged = {**extra, **metadata} or None

        with self._db_session() as session:
            entity = session.scalar(
                select(DocumentEntity).where(DocumentEntity.document_id == document_id)
            )
            if entity is None:
                entity = DocumentEntity(
                    document_id=document_id,
                    file_name=columns.get("file_name", ""),
                    file_type=columns.get("file_type", "txt"),
                    file_size=int(columns.get("file_size", 0) or 0),
                    status=columns.get("status", "pending"),
                    chunk_count=int(columns.get("chunk_count", 0) or 0),
                    content_key=columns.get("content_key", ""),
                    storage_backend=columns.get("storage_backend", "local"),
                    content_url=columns.get("content_url"),
                    checksum=columns.get("checksum"),
                    extra=extra_merged,
                    created_at=columns.get("created_at") or now,
                    updated_at=columns.get("updated_at") or now,
                )
                session.add(entity)
            else:
                for key, value in columns.items():
                    if key == "document_id":
                        continue
                    setattr(entity, key, value)
                if extra_merged:
                    entity.extra = {**(entity.extra or {}), **extra_merged}
                entity.updated_at = now
        return document_id

    def update(self, document_id: str, data: dict[str, Any]) -> None:
        """更新文档元数据（仅更新 data 中提供的字段；未知字段并入 metadata）。"""
        self._ensure_initialized()
        columns, extra, metadata = _split_fields(data)
        now = datetime.now(UTC)
        extra_merged = {**extra, **metadata}

        with self._db_session() as session:
            entity = session.scalar(
                select(DocumentEntity).where(DocumentEntity.document_id == document_id)
            )
            if entity is None:
                logger.warning(f"DocumentRepository.update: document {document_id} not found, skip")
                return
            for key, value in columns.items():
                setattr(entity, key, value)
            if extra_merged:
                entity.extra = {**(entity.extra or {}), **extra_merged}
            entity.updated_at = now

    def delete(self, document_id: str) -> None:
        """删除文档元数据（内容对象由 services 层协调删除）。"""
        self._ensure_initialized()
        with self._db_session() as session:
            entity = session.scalar(
                select(DocumentEntity).where(DocumentEntity.document_id == document_id)
            )
            if entity is not None:
                session.delete(entity)

    # ── 读操作 ──────────────────────────────────────────────
    def load(self, document_id: str) -> dict[str, Any] | None:
        """按文档 ID 加载元数据（返回 dict，键与旧 JSON 存储兼容）。"""
        self._ensure_initialized()
        with self._db_session() as session:
            entity = session.scalar(
                select(DocumentEntity).where(DocumentEntity.document_id == document_id)
            )
            if entity is None:
                return None
            return self._to_dict(entity)

    def list_all(self) -> list[dict[str, Any]]:
        """列出所有文档。"""
        self._ensure_initialized()
        with self._db_session() as session:
            entities = session.scalars(
                select(DocumentEntity).order_by(DocumentEntity.created_at.desc())
            ).all()
            return [self._to_dict(e) for e in entities]

    def list_page(
        self,
        skip: int = 0,
        limit: int | None = None,
        status: str | None = None,
        file_type: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """分页列出文档（过滤与分页下推到数据库层）。

        Returns:
            tuple[list[dict[str, Any]], int]: (当前页文档列表, 匹配总数)
        """
        self._ensure_initialized()
        with self._db_session() as session:
            conditions = []
            if status:
                conditions.append(DocumentEntity.status == status)
            if file_type:
                conditions.append(DocumentEntity.file_type == file_type)

            total = session.scalar(
                select(func.count(DocumentEntity.id)).where(*conditions)
            ) or 0

            stmt = (
                select(DocumentEntity)
                .where(*conditions)
                .order_by(DocumentEntity.created_at.desc())
                .offset(skip)
            )
            if limit is not None:
                stmt = stmt.limit(limit)
            entities = session.scalars(stmt).all()
            return [self._to_dict(e) for e in entities], int(total)

    def exists(self, document_id: str) -> bool:
        """检查文档元数据是否存在。"""
        self._ensure_initialized()
        with self._db_session() as session:
            count = session.scalar(
                select(func.count(DocumentEntity.id)).where(
                    DocumentEntity.document_id == document_id
                )
            )
            return int(count or 0) > 0

    # ── 内容对象辅助（对象存储） ─────────────────────────────
    @property
    def storage(self) -> StorageProvider:
        """内容对象存储提供者（供 services 层写入 / 删除 / 生成 URL）。"""
        return self._storage

    @staticmethod
    def make_checksum(data: bytes) -> str:
        """计算内容 SHA-256 校验和。"""
        return hashlib.sha256(data).hexdigest()

    # ── 内部 ────────────────────────────────────────────────
    def _db_session(self):
        """获取数据库会话上下文（自动提交 / 回滚 / 关闭）。

        测试注入 session 时直接复用（不代为提交）。
        """
        if self._session is not None:
            return _ExternalSessionScope(self._session)
        return get_cached_database_provider().session()

    @staticmethod
    def _to_dict(entity: DocumentEntity) -> dict[str, Any]:
        return {
            "document_id": entity.document_id,
            "file_name": entity.file_name,
            "file_type": entity.file_type,
            "file_size": entity.file_size,
            "status": entity.status,
            "chunk_count": entity.chunk_count,
            "content_key": entity.content_key,
            "storage_backend": entity.storage_backend,
            "content_url": entity.content_url,
            "checksum": entity.checksum,
            "metadata": entity.extra or {},
            "created_at": entity.created_at.isoformat() if entity.created_at else None,
            "updated_at": entity.updated_at.isoformat() if entity.updated_at else None,
        }

    def _ensure_initialized(self) -> None:
        """确保已初始化。"""
        if not self._initialized:
            raise RuntimeError("DocumentRepository not initialized. Call initialize() first.")


class _ExternalSessionScope:
    """测试注入 session 的兼容上下文（不代为 commit/close）。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def __enter__(self) -> Session:
        return self._session

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            self._session.rollback()
