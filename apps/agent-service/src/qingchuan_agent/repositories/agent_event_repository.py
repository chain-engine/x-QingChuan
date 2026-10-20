#!/usr/bin/env python3
"""Agent 事件仓储（数据访问层，无业务逻辑，对齐北辰 repositories/agent_event_repository）。"""

from __future__ import annotations

from sqlalchemy import desc

from qingchuan_agent.models.entities.agent_event import AgentEvent
from qingchuan_agent.repositories.base_repository import BaseRepository


class AgentEventRepository(BaseRepository[AgentEvent]):
    """AgentEvent 表数据访问。

    协作事件查询（审计面板）；写入由 services 层在事件双写链路中调用。
    """

    model_class = AgentEvent

    def list_by_type(self, event_type: str, offset: int = 0, limit: int = 20) -> list[AgentEvent]:
        """按事件类型分页查询。"""
        return self.list(
            AgentEvent.event_type == event_type,
            order_by=desc(AgentEvent.id),
            offset=offset,
            limit=limit,
        )

    def list_recent(self, offset: int = 0, limit: int = 20) -> list[AgentEvent]:
        """最近事件（按创建时间倒序）。"""
        return self.list(order_by=desc(AgentEvent.id), offset=offset, limit=limit)


__all__ = ["AgentEventRepository"]
