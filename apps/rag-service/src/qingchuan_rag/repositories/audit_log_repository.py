#!/usr/bin/env python3
"""业务审计日志仓库。

审计日志为只追加流水，不提供更新 / 删除操作；提供按条件分页搜索。
事务边界（commit / rollback）由 services 层统一管理，仓库只做数据访问。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from qingchuan_rag.models.audit_log_entity import AuditLogEntity


class AuditLogRepository:
    """审计日志数据访问实现（session 由 services 层传入 / 创建）。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    # ── 写入 ──────────────────────────────────────────────
    def create(
        self,
        *,
        entity_type: str,
        entity_id: str | None,
        action: str,
        operator_id: str | None = None,
        operator_name: str | None = None,
        before_data: dict[str, Any] | None = None,
        after_data: dict[str, Any] | None = None,
        ip_address: str | None = None,
        remarks: str | None = None,
    ) -> AuditLogEntity:
        """追加一条审计记录（只追加，不更新）。"""
        entity = AuditLogEntity(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            operator_id=operator_id,
            operator_name=operator_name,
            before_data=before_data,
            after_data=after_data,
            ip_address=ip_address,
            remarks=remarks,
        )
        self._session.add(entity)
        self._session.flush()
        return entity

    # ── 查询 ──────────────────────────────────────────────
    def get_by_id(self, log_id: int) -> AuditLogEntity | None:
        """按主键查询单条审计记录。"""
        return self._session.get(AuditLogEntity, log_id)

    def search(
        self,
        entity_type: str | None = None,
        action: str | None = None,
        operator_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        keyword: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[AuditLogEntity], int]:
        """按条件搜索审计日志（创建时间倒序分页）。

        Args:
            entity_type: 按实体类型过滤
            action: 按操作类型过滤
            operator_id: 按操作者 AppId 过滤
            start_time / end_time: 时间范围过滤
            keyword: 关键字，模糊匹配实体类型 / 操作 / 实体ID / 操作者 / IP / 备注
            skip / limit: 分页

        Returns:
            (当前页实体列表, 匹配总数)
        """
        conditions: list[Any] = []
        if entity_type:
            conditions.append(AuditLogEntity.entity_type == entity_type)
        if action:
            conditions.append(AuditLogEntity.action == action)
        if operator_id:
            conditions.append(AuditLogEntity.operator_id == operator_id)
        if start_time:
            conditions.append(AuditLogEntity.created_at >= start_time)
        if end_time:
            conditions.append(AuditLogEntity.created_at <= end_time)
        if keyword and keyword.strip():
            kw = keyword.strip()
            conditions.append(
                or_(
                    AuditLogEntity.entity_type.contains(kw),
                    AuditLogEntity.action.contains(kw),
                    AuditLogEntity.entity_id.contains(kw),
                    AuditLogEntity.operator_id.contains(kw),
                    AuditLogEntity.operator_name.contains(kw),
                    AuditLogEntity.ip_address.contains(kw),
                    AuditLogEntity.remarks.contains(kw),
                )
            )

        base = select(AuditLogEntity)
        if conditions:
            base = base.where(*conditions)
        total = self._session.execute(
            select(func.count()).select_from(base.subquery())
        ).scalar_one()
        stmt = base.order_by(AuditLogEntity.id.desc()).offset(skip).limit(limit)
        return list(self._session.execute(stmt).scalars().all()), total

    # ── 事务边界（供 services 层统一管理事务）─────────────────
    def commit(self) -> None:
        """提交当前事务（由 services 层调用）。"""
        self._session.commit()

    def rollback(self) -> None:
        """回滚当前事务（由 services 层调用）。"""
        self._session.rollback()

    def close(self) -> None:
        """关闭会话（由 services 层调用）。"""
        self._session.close()


__all__ = ["AuditLogRepository"]
