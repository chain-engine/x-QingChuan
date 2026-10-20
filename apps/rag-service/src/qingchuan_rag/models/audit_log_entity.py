#!/usr/bin/env python3
"""业务审计日志实体模型（参考汉江 x-HanJiang audit_logs 设计，适配观海）。

观海无 int 用户体系，操作人为开放平台应用（AppId 字符串）：
- operator_id:   调用方 AppId（如 gh_xxxx / app），而非用户表主键；
- operator_name: 操作人名称快照（查询展示用，晴川内部固定为 internal）。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from qingchuan_rag.infras.database import Base


class AuditLogEntity(Base):
    """业务审计日志表。"""

    __tablename__ = "audit_logs"
    # 主键用 Integer：SQLite 仅 INTEGER PRIMARY KEY 支持自动自增（rowid 别名），
    # BIGINT 主键在 SQLite 下不会自增导致 NOT NULL 失败；MySQL 下 INT AUTO_INCREMENT 等价。
    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, comment="审计日志ID"
    )
    entity_type: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="实体类型，如 document/rag_query/sync_task"
    )
    entity_id: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="实体ID")
    action: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="操作类型，如 upload/delete/create/revoke/enable/query"
    )
    operator_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="操作者 AppId"
    )
    operator_name: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="操作者应用名快照"
    )
    before_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True, comment="变更前数据"
    )
    after_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True, comment="变更后数据"
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True, comment="操作IP")
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        comment="创建时间",
    )
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True, comment="备注")
    __table_args__ = (
        Index("idx_audit_created_at", "created_at"),
        Index("idx_audit_entity", "entity_type", "entity_id"),
        Index("idx_audit_operator", "operator_id"),
    )


__all__ = ["AuditLogEntity"]
