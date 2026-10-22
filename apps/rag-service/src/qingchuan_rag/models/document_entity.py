#!/usr/bin/env python3
"""文档元数据实体模型（方案 A：元数据入库）。

文档【元数据】落业务库 MySQL（本地开发可回退 SQLite），
文档【内容】经 infras/storage.py 存储抽象层落对象存储
（本地文件系统 / S3 兼容对象存储），本表仅保存内容引用
（content_key + storage_backend），不存正文。

与 SyncTaskEntity 共用同一 ORM 范式（Base / Integer 主键 /
String + JSON + server_default 时间戳），MySQL 与 SQLite 双后端平滑切换。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from qingchuan_rag.infras.database import Base


class DocumentEntity(Base):
    """文档元数据表。"""

    __tablename__ = "documents"
    # 主键用 Integer：SQLite 仅 INTEGER PRIMARY KEY 支持自动自增（rowid 别名），
    # BIGINT 主键在 SQLite 下不会自增导致 NOT NULL 失败；MySQL 下 INT AUTO_INCREMENT 等价。
    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, comment="文档记录ID"
    )
    document_id: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, comment="文档唯一ID（业务标识）"
    )
    file_name: Mapped[str] = mapped_column(
        String(255), nullable=False, default="", comment="文件名"
    )
    file_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="txt", comment="文件类型 txt/md/pdf/docx/html"
    )
    file_size: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="文件大小（字节）"
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        comment="处理状态 pending/processing/completed/failed",
    )
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="切分块数")
    # 内容对象引用：对象存储 key（本地存储为 data 目录下相对路径）
    content_key: Mapped[str] = mapped_column(
        String(512), nullable=False, default="", comment="内容对象存储键（对象存储/本地相对路径）"
    )
    storage_backend: Mapped[str] = mapped_column(
        String(20), nullable=False, default="local", comment="内容存储后端 local/s3"
    )
    content_url: Mapped[str | None] = mapped_column(
        String(1024), nullable=True, comment="内容访问 URL（动态生成时为 null，按需计算）"
    )
    checksum: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="内容 SHA-256 校验和（可选）"
    )
    extra: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True, comment="扩展元数据（来源、分类等；兼容 SyncTaskEntity 范式）"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        comment="创建时间",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        comment="更新时间",
    )
    __table_args__ = (
        Index("idx_documents_status", "status"),
        Index("idx_documents_created_at", "created_at"),
    )


__all__ = ["DocumentEntity"]
