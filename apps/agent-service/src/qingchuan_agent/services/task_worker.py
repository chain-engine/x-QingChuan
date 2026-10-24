#!/usr/bin/env python3
"""Agent 任务 Worker（晴川 x-QingChuan agent-service）。

消费 Redis Stream 任务队列，替代请求内线程池执行：
    - submit 消息：加载任务 → AgentRuntime.invoke_task（线程池内跑同步图）→
      回写任务状态/结果 → 编排事件双写 → 发布 task.state 事件（SSE/轮询可见）
    - resume 消息：加载任务 → AgentRuntime.resume_task（人工接管续跑）→ 同上

可靠性：
    - 处理完成后 ACK 消息，崩溃后消息留在 pending 由其它消费者认领
      （当前为单消费者简化版；多副本可基于 XAUTOCLAIM 增强）
    - worker 每次消费独立 Session，不与请求共享（SQLAlchemy Session 非线程安全）
    - 单条消息异常不回滚整批：回写 failed + 落库错误事件后 ACK，避免死循环
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from qingchuan_agent.agents.runtime import AgentRuntime, get_agent_runtime
from qingchuan_agent.constants import TaskStatus
from qingchuan_agent.core.logger import logger
from qingchuan_agent.infras.event_bus import EventBus, EventMessage, get_event_bus
from qingchuan_agent.infras.task_stream import DEFAULT_CONSUMER, TaskStreamQueue
from qingchuan_agent.models.entities.agent_event import AgentEvent
from qingchuan_agent.repositories.agent_event_repository import AgentEventRepository
from qingchuan_agent.repositories.agent_task_repository import AgentTaskRepository
from qingchuan_agent.services.task_execution import (
    invoke_and_finalize,
    resume_and_finalize,
)

# task.state 事件类型（SSE / 轮询统一消费；审计面板可查）
TASK_STATE_EVENT: str = "task.state"


class TaskWorker:
    """Redis Stream 任务消费者（lifespan 启动的常驻协程）。"""

    def __init__(
        self,
        queue: TaskStreamQueue,
        session_factory: Callable[[], Session],
        runtime: AgentRuntime | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._queue = queue
        self._session_factory = session_factory
        self._runtime: AgentRuntime = runtime or get_agent_runtime()
        self._event_bus: EventBus = event_bus or get_event_bus()
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    async def run_forever(self, consumer: str = DEFAULT_CONSUMER) -> None:
        """常驻消费循环：拉消息 → 处理 → ACK（异常消息也 ACK，避免 pending 卡死）。"""
        self._running = True
        logger.info(f"[TaskWorker] 启动：consumer={consumer} stream={self._queue.stream}")
        try:
            while self._running:
                messages = await self._queue.dequeue(consumer=consumer)
                if not messages:
                    continue
                for msg_id, fields in messages:
                    try:
                        await self._process(fields)
                    except Exception as exc:
                        logger.exception(f"[TaskWorker] 消息处理失败（msg={msg_id}）：{exc}")
                    finally:
                        await self._queue.ack(msg_id)
        except asyncio.CancelledError:
            logger.info("[TaskWorker] 收到取消，退出消费循环")
            raise
        finally:
            self._running = False

    async def stop(self) -> None:
        """停止消费循环（lifespan shutdown 调用）。"""
        self._running = False

    async def _process(self, fields: dict[str, Any]) -> None:
        action = str(fields.get("action") or "")
        if action == "submit":
            await self._handle_submit(fields)
        elif action == "resume":
            await self._handle_resume(fields)
        else:
            logger.warning(f"[TaskWorker] 未知 action，跳过：{action}")

    # ----------------------------------------------------------
    # 处理路径
    # ----------------------------------------------------------

    async def _handle_submit(self, fields: dict[str, Any]) -> None:
        task_id = int(fields["task_id"])
        session = self._session_factory()
        try:
            task_repo = AgentTaskRepository(session)
            event_repo = AgentEventRepository(session)
            task = task_repo.get(task_id)
            if task is None:
                logger.error(f"[TaskWorker] 任务不存在（已删除？）：{task_id}")
                return
            task_type = str(fields.get("task_type") or task.task_type)
            payload: dict[str, Any] = fields.get("payload") or task.payload or {}
            thread_id = str(fields.get("thread_id") or task.thread_id or f"task:{task_id}")

            await self._publish_task_state(task_repo, event_repo, task_id, TaskStatus.RUNNING.mark)
            await invoke_and_finalize(
                runtime=self._runtime,
                task_repo=task_repo,
                event_repo=event_repo,
                event_bus=self._event_bus,
                task=task,
                task_type=None if task_type == "auto" else task_type,
                payload=payload,
                thread_id=thread_id,
            )
            await self._publish_task_state(
                task_repo, event_repo, task_id, task.status or TaskStatus.SUCCESS.mark
            )
            task_repo.commit()
        finally:
            session.close()

    async def _handle_resume(self, fields: dict[str, Any]) -> None:
        task_id = int(fields["task_id"])
        session = self._session_factory()
        try:
            task_repo = AgentTaskRepository(session)
            event_repo = AgentEventRepository(session)
            task = task_repo.get(task_id)
            if task is None:
                logger.error(f"[TaskWorker] 恢复任务不存在：{task_id}")
                return
            update = {
                "decision": str(fields.get("decision") or "approve"),
                "remark": fields.get("remark") or None,
                "extra": fields.get("extra") or {},
            }
            await self._publish_task_state(task_repo, event_repo, task_id, TaskStatus.RUNNING.mark)
            await resume_and_finalize(
                runtime=self._runtime,
                task_repo=task_repo,
                event_repo=event_repo,
                event_bus=self._event_bus,
                task=task,
                update=update,
            )
            await self._publish_task_state(
                task_repo, event_repo, task_id, task.status or TaskStatus.SUCCESS.mark
            )
            task_repo.commit()
        finally:
            session.close()

    # ----------------------------------------------------------
    # 状态事件
    # ----------------------------------------------------------

    async def _publish_task_state(
        self,
        task_repo: AgentTaskRepository,
        event_repo: AgentEventRepository,
        task_id: int,
        status: str,
    ) -> None:
        """发布 task.state 事件（落库 + 总线广播），SSE 端据此流式推送。"""
        event = AgentEvent(
            event_type=TASK_STATE_EVENT,
            source_agent=None,
            target_agent=None,
            payload={"task_id": task_id, "status": status, "ts": datetime.now(UTC).isoformat()},
            status="recorded",
        )
        event_repo.add(event)
        try:
            await self._event_bus.publish(
                EventMessage(
                    event_type=TASK_STATE_EVENT,
                    payload={
                        "task_id": task_id,
                        "status": status,
                        "ts": datetime.now(UTC).isoformat(),
                    },
                )
            )
        except Exception as exc:
            logger.exception(f"[TaskWorker] task.state 发布失败（已落库）：{exc}")
        # 交由调用方 commit；不在此处提交以保持事务粒度


__all__ = ["TASK_STATE_EVENT", "TaskWorker"]
