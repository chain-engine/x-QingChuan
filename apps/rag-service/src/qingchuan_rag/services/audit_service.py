#!/usr/bin/env python3
"""业务审计服务（记录"谁在什么时间改了什么数据"，落库留痕、只追加）。

职责：
- log_event：记录"谁在什么时间改了什么数据"（只追加，写失败仅告警不阻断业务）；
- search / get_by_id：审计日志查询（管理面接口复用）。

事务边界：每次 log_event / search 使用独立会话（get_session），
自身管理提交 / 回滚 / 关闭——审计与业务事务解耦：
业务失败时审计仍保留"尝试了该操作"的记录；审计写失败不影响业务主流程。

操作人约定：operator 为 dict，由 api 层解析后传入（services 禁止读取 request 对象）：
    {"operator_id": AppId, "operator_name": 应用名, "ip_address": 来源IP}
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from qingchuan_rag.core.logger import logger
from qingchuan_rag.infras.database import get_session
from qingchuan_rag.repositories.audit_log_repository import AuditLogRepository


class AuditService:
    """审计日志服务。"""

    def __init__(self, repository: AuditLogRepository | None = None) -> None:
        # 无状态设计：不持有会话，每次操作独立创建，避免跨线程共享 Session
        self._repository_factory = repository or AuditLogRepository

    # ── 写入 ──────────────────────────────────────────────
    def log_event(
        self,
        entity_type: str,
        entity_id: str | int | None,
        action: str,
        operator: dict[str, Any] | None = None,
        before_data: dict[str, Any] | None = None,
        after_data: dict[str, Any] | None = None,
        remarks: str | None = None,
    ) -> None:
        """写入一条审计记录（独立事务，写失败仅告警不阻断业务）。

        Args:
            entity_type: 实体类型，如 document / rag_query / sync_task
            entity_id: 实体ID
            action: 操作类型，如 upload / delete / create / revoke / enable / query
            operator: 操作人上下文（operator_id / operator_name / ip_address），可为 None（系统操作）
            before_data: 变更前数据快照（JSON 可序列化）
            after_data: 变更后数据快照（JSON 可序列化）
            remarks: 备注
        """
        operator = operator or {}
        session = get_session()
        try:
            repo = self._repository_factory(session=session)
            repo.create(
                entity_type=entity_type,
                entity_id=str(entity_id) if entity_id is not None else None,
                action=action,
                operator_id=operator.get("operator_id"),
                operator_name=operator.get("operator_name"),
                before_data=before_data,
                after_data=after_data,
                ip_address=operator.get("ip_address"),
                remarks=remarks,
            )
            repo.commit()
            logger.debug(
                "Audit log: entity_type=%s entity_id=%s action=%s operator_id=%s",
                entity_type,
                entity_id,
                action,
                operator.get("operator_id"),
            )
        except Exception as exc:  # noqa: BLE001 - 审计失败不阻断业务
            session.rollback()
            logger.warning(
                "Audit log write failed for entity_type=%s entity_id=%s action=%s: %s",
                entity_type,
                entity_id,
                action,
                exc,
            )
        finally:
            session.close()

    # ── 查询 ──────────────────────────────────────────────
    def search(
        self,
        entity_type: str | None = None,
        action: str | None = None,
        operator_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """按条件分页搜索审计日志（创建时间倒序）。

        Returns:
            {"items": [...], "total": ..., "page": ..., "page_size": ...}
        """
        page = max(1, page)
        page_size = min(max(1, page_size), 100)
        session = get_session()
        try:
            repo = self._repository_factory(session=session)
            items, total = repo.search(
                entity_type=entity_type,
                action=action,
                operator_id=operator_id,
                start_time=start_time,
                end_time=end_time,
                keyword=keyword,
                skip=(page - 1) * page_size,
                limit=page_size,
            )
            return {
                "items": [self._to_dict(e) for e in items],
                "total": total,
                "page": page,
                "page_size": page_size,
            }
        finally:
            session.close()

    def get_by_id(self, log_id: int) -> dict[str, Any] | None:
        """按 ID 查询单条审计记录。"""
        session = get_session()
        try:
            repo = self._repository_factory(session=session)
            entity = repo.get_by_id(log_id)
            return self._to_dict(entity) if entity else None
        finally:
            session.close()

    @staticmethod
    def _to_dict(entity: Any) -> dict[str, Any]:
        """实体 → 响应字典（created_at 转 ISO 字符串，保证 JSON 可序列化）。"""
        return {
            "id": entity.id,
            "entity_type": entity.entity_type,
            "entity_id": entity.entity_id,
            "action": entity.action,
            "operator_id": entity.operator_id,
            "operator_name": entity.operator_name,
            "before_data": entity.before_data,
            "after_data": entity.after_data,
            "ip_address": entity.ip_address,
            "created_at": entity.created_at.isoformat() if entity.created_at else None,
            "remarks": entity.remarks,
        }


__all__ = ["AuditService"]
