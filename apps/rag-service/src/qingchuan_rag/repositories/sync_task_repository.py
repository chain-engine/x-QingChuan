#!/usr/bin/env python3
"""人社数据同步任务仓库。

同步任务为"创建 → 更新状态"的流水式记录，仓库只做数据访问，
事务边界（commit / rollback）由 services 层统一管理。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from qingchuan_rag.models.sync_task_entity import SyncTaskEntity


class SyncTaskRepository:
    """同步任务数据访问实现（session 由 services 层传入 / 创建）。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    # ── 写入 ──────────────────────────────────────────────
    def create(
        self,
        *,
        task_id: str,
        status: str = "pending",
        channel: str = "manual",
        full: bool = False,
        source: str = "hrss",
        started_at: datetime | None = None,
        extra: dict[str, Any] | None = None,
    ) -> SyncTaskEntity:
        """创建一条同步任务记录。"""
        entity = SyncTaskEntity(
            task_id=task_id,
            status=status,
            channel=channel,
            full=full,
            source=source,
            started_at=started_at,
            extra=extra,
        )
        self._session.add(entity)
        self._session.flush()
        return entity

    def update_status(
        self,
        *,
        entity: SyncTaskEntity | None = None,
        task_id: str | None = None,
        status: str,
        total_records: int | None = None,
        synced_records: int | None = None,
        failed_records: int | None = None,
        message: str | None = None,
        error: str | None = None,
        finished_at: datetime | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """更新任务状态字段（未提交字段则保持不变）。"""
        if entity is None and task_id is None:
            raise ValueError("update_status 需要 entity 或 task_id 之一")
        if entity is None:
            entity = self._session.execute(
                select(SyncTaskEntity).where(SyncTaskEntity.task_id == task_id)
            ).scalar_one_or_none()
        if entity is None:
            return
        entity.status = status
        if total_records is not None:
            entity.total_records = total_records
        if synced_records is not None:
            entity.synced_records = synced_records
        if failed_records is not None:
            entity.failed_records = failed_records
        if message is not None:
            entity.message = message
        if error is not None:
            entity.error = error
        if finished_at is not None:
            entity.finished_at = finished_at
        if extra is not None:
            entity.extra = extra
        self._session.flush()

    # ── 查询 ──────────────────────────────────────────────
    def get_by_task_id(self, task_id: str) -> SyncTaskEntity | None:
        """按业务任务 ID 查询。"""
        return self._session.execute(
            select(SyncTaskEntity).where(SyncTaskEntity.task_id == task_id)
        ).scalar_one_or_none()

    def get_latest(self, limit: int = 1) -> list[SyncTaskEntity]:
        """查询最近的任务记录（按创建时间倒序）。"""
        stmt = select(SyncTaskEntity).order_by(SyncTaskEntity.id.desc()).limit(limit)
        return list(self._session.execute(stmt).scalars().all())

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


__all__ = ["SyncTaskRepository"]
