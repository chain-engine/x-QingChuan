#!/usr/bin/env python3
"""任务执行公共逻辑（晴川 x-QingChuan agent-service）。

AgentTaskService 与 TaskWorker 共用的「执行 → 回写 → 事件双写」路径，
避免两处复制状态机流转规则：

    invoke_and_finalize  /  resume_and_finalize
        调 AgentRuntime 执行 → 回写任务实体 → 编排事件落库 + 总线广播
    apply_final_state
        编排最终状态 → 任务实体（status / assignee / result / error / retry）
    persist_and_publish_events
        编排事件双写：agent_events 落库 + EventBus publish（失败不阻断）

约定：本模块函数操作「传入的 session 及其 repo」，不负责 commit；
调用方（service / worker）各自 commit 并管理会话生命周期。
"""

from __future__ import annotations

import asyncio
from typing import Any

from qingchuan_agent.agents.runtime import AgentRuntime
from qingchuan_agent.constants import TaskStatus
from qingchuan_agent.core.logger import logger
from qingchuan_agent.infras.event_bus import EventBus, EventMessage
from qingchuan_agent.models.entities.agent_event import AgentEvent
from qingchuan_agent.models.entities.agent_task import AgentTask
from qingchuan_agent.repositories.agent_event_repository import AgentEventRepository
from qingchuan_agent.repositories.agent_task_repository import AgentTaskRepository


async def invoke_and_finalize(
    runtime: AgentRuntime,
    task_repo: AgentTaskRepository,
    event_repo: AgentEventRepository,
    event_bus: EventBus,
    task: AgentTask,
    task_type: str | None,
    payload: dict[str, Any],
    thread_id: str,
) -> None:
    """提交路径：执行 invoke → 回写任务 → 事件双写（worker 与同步回退共用）。"""
    loop = asyncio.get_running_loop()
    final_state = await loop.run_in_executor(
        None,
        lambda: runtime.invoke_task(
            task_type=task_type,
            payload=payload,
            thread_id=thread_id,
            task_id=task.id,
        ),
    )
    apply_final_state(task, final_state, thread_id)
    await persist_and_publish_events(event_repo, event_bus, final_state)


async def resume_and_finalize(
    runtime: AgentRuntime,
    task_repo: AgentTaskRepository,
    event_repo: AgentEventRepository,
    event_bus: EventBus,
    task: AgentTask,
    update: dict[str, Any],
) -> None:
    """恢复路径：人工接管 resume → 回写任务 → 事件双写。"""
    if not task.thread_id:
        from qingchuan_agent.core.exceptions import ValidationError

        raise ValidationError("任务无线程 ID，无法恢复（可能未执行或已完成）")
    loop = asyncio.get_running_loop()
    final_state = await loop.run_in_executor(
        None,
        lambda: runtime.resume_task(task.thread_id, update),
    )
    apply_final_state(task, final_state, task.thread_id)
    await persist_and_publish_events(event_repo, event_bus, final_state)


def apply_final_state(task: AgentTask, final_state: dict[str, Any], thread_id: str) -> None:
    """把编排图最终状态回写到任务实体。"""
    task.thread_id = thread_id
    task.status = final_state.get("status", TaskStatus.SUCCESS.mark)
    task.assignee_agent = final_state.get("target_agent")  # 路由结果回写（Agent 归属可查）
    task.result = final_state.get("result") or final_state
    task.error_message = final_state.get("error")
    task.timeout_at = None
    if final_state.get("status") == TaskStatus.FAILED.mark:
        task.retry_count += 1
    logger.info(
        f"[TaskExec] 任务结束：id={task.id} status={task.status} assignee={task.assignee_agent}"
    )


async def persist_and_publish_events(
    event_repo: AgentEventRepository,
    event_bus: EventBus,
    final_state: dict[str, Any],
) -> None:
    """事件双写：agent_events 落库 + EventBus publish（失败仅记日志不阻断）。"""
    for event in final_state.get("events", []):
        event_repo.add(
            AgentEvent(
                event_type=event.get("type", "unknown"),
                source_agent=event.get("source"),
                target_agent=event.get("target"),
                payload=event.get("payload"),
                status="recorded",
            )
        )
        try:
            await event_bus.publish(
                EventMessage(
                    event_type=event.get("type", "unknown"),
                    payload=event.get("payload") or {},
                    source_agent=event.get("source"),
                    target_agent=event.get("target"),
                )
            )
        except Exception as exc:  # 总线发布失败不影响主流程
            logger.exception(f"[TaskExec] 事件发布失败（已落库留痕）：{exc}")


__all__ = [
    "apply_final_state",
    "invoke_and_finalize",
    "persist_and_publish_events",
    "resume_and_finalize",
]
