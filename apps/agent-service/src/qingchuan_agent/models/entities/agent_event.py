#!/usr/bin/env python3
"""Agent 事件表 ORM 实体（晴川 x-QingChuan，对齐北辰 models/entities/agent_event）。

协作事件留痕（审计面板）：Agent 间协作、人工接管、编排关键节点事件。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from qingchuan_agent.infras.database import Base


class AgentEvent(Base):
    """Agent 协作事件实体（对应 agent_events 表）。"""

    __tablename__ = "agent_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="主键")
    event_type: Mapped[str] = mapped_column(
        String(32), index=True, nullable=False, comment="事件类型"
    )
    source_agent: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="来源 Agent 类型"
    )
    target_agent: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="目标 Agent 类型"
    )
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="事件载荷")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="recorded", comment="事件状态"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), comment="创建时间"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AgentEvent id={self.id} type={self.event_type} status={self.status}>"
