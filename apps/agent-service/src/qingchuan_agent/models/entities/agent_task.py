#!/usr/bin/env python3
"""Agent 任务表 ORM 实体（晴川 x-QingChuan，对齐北辰 models/entities/agent_task）。

一张表承载编排中枢的全部任务：任务类型（路由键）、状态机、重试、线程 ID、
执行结果与错误信息。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from qingchuan_agent.infras.database import Base


class AgentTask(Base):
    """Agent 任务实体（对应 agent_tasks 表）。"""

    __tablename__ = "agent_tasks"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, comment="主键"
    )
    task_type: Mapped[str] = mapped_column(
        String(32), index=True, nullable=False, comment="任务类型（AgentType）"
    )
    payload: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict, comment="任务入参（各 Agent 自定义）"
    )
    status: Mapped[str] = mapped_column(
        String(20),
        index=True,
        nullable=False,
        default="pending",
        comment="任务状态（TaskStatus）",
    )
    assignee_agent: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="实际派发的 Agent 类型"
    )
    thread_id: Mapped[str | None] = mapped_column(
        String(64),
        index=True,
        nullable=True,
        comment="LangGraph 线程 ID（checkpoint 断点续跑）",
    )
    retry_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="已重试次数"
    )
    max_retries: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3, comment="最大重试次数"
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="最近一次失败原因"
    )
    result: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="执行结果（含各 Agent 自定义凭证）"
    )
    timeout_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="超时时间点"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AgentTask id={self.id} type={self.task_type} status={self.status}>"
