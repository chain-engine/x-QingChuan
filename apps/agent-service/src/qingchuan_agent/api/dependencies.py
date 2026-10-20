#!/usr/bin/env python3
"""API 跨域公共依赖注入模块（晴川 x-QingChuan，对齐北辰 api/dependencies）。

提供 FastAPI 依赖：
    - get_db: 请求级数据库会话（DB 未启用时明确报 503，提示接入方式）
    - get_task_service: Agent 任务服务（任务提交/查询/人工接管/事件查询）

数据流向约束：api 层只做参数解析与依赖装配，业务逻辑全部下沉 services。
"""

from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from qingchuan_agent.core.config import settings
from qingchuan_agent.infras.database import get_cached_database_provider
from qingchuan_agent.services.agent_task_service import AgentTaskService


def get_db() -> Generator[Session]:
    """请求级数据库会话依赖（未启用时给出明确接入提示）。"""
    if not settings.database.enabled:
        raise HTTPException(
            status_code=503,
            detail="数据库未启用：请设置 QINGCHUAN_AGENT_DATABASE_ENABLED=true 并配置 "
            "QINGCHUAN_AGENT_DATABASE_HOST/PORT/USER/PASSWORD/DATABASE",
        )
    provider = get_cached_database_provider()
    session = provider.get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_task_service(
    session: Session = Depends(get_db),
) -> AgentTaskService:
    """Agent 任务服务依赖（任务提交 / 查询 / 人工接管 / 事件查询）。"""
    return AgentTaskService(session)


__all__ = ["get_db", "get_task_service"]
