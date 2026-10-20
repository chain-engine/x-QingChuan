#!/usr/bin/env python3
"""人社数据同步任务状态实体模型。

记录每次同步触发（手动 / 周期调度）的执行状态，落业务库 MySQL
（本地开发可回退 SQLite），供触发接口与状态查询使用。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from qingchuan_rag.infras.database import Base


class SyncTaskEntity(Base):
    """人社数据同步任务表。"""

    __tablename__ = "sync_tasks"
    # 主键用 Integer：SQLite 仅 INTEGER PRIMARY KEY 支持自动自增（rowid 别名），
    # BIGINT 主键在 SQLite 下不会自增导致 NOT NULL 失败；MySQL 下 INT AUTO_INCREMENT 等价。
    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, comment="同步任务ID"
    )
    task_id: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, comment="同步任务唯一ID（业务标识）"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", comment="任务状态 pending/running/success/failed"
    )
    channel: Mapped[str] = mapped_column(
        String(20), nullable=False, default="manual", comment="触发渠道 manual/scheduler"
    )
    full: Mapped[bool] = mapped_column(default=False, comment="是否全量同步")
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="hrss", comment="数据源标识")
    total_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="待同步记录总数")
    synced_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="成功同步记录数")
    failed_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="失败记录数")
    message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="执行说明 / 错误摘要")
    error: Mapped[str | None] = mapped_column(Text, nullable=True, comment="失败明细")
    extra: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True, comment="扩展字段（批次信息等）")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="开始时间")
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="结束时间")
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        comment="创建时间",
    )
    __table_args__ = (
        Index("idx_sync_status", "status"),
        Index("idx_sync_created_at", "created_at"),
    )


__all__ = ["SyncTaskEntity"]
