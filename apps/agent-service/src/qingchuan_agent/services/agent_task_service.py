#!/usr/bin/env python3
"""Agent 任务服务（晴川 x-QingChuan 业务层，对齐北辰 services/agent_task_service）。

职责边界（api → services → repositories 单向）：
    - 任务提交：落库（running）→ Redis Stream 入队（异步执行，接口立即返回）/
      无 Redis 时同步回退 → worker 执行并回写状态/结果 → 事件落库
    - 任务查询：列表 / 详情（管理后台）
    - 人工接管：interrupt 断点 → resume 恢复（走同一任务队列）→ 回写人工决策
    - 事件查询：协作事件分页（审计面板）
    - 不读取 Request 对象；HTTP 参数由 api 层解析后传入

执行模型（用户已拍板「异步化」）：
    Redis 可用：提交只落库 + XADD 入队即返回；TaskWorker（lifespan 启动）消费执行，
    状态/结果由 worker 回写，SSE / 轮询 GET /tasks/{id} 获取结果。
    Redis 不可用（开发/降级）：保留线程池同步执行回退，行为与旧版一致。

说明：真正的"编排执行"在 AgentRuntime（图编译 / invoke / resume），
本服务是任务门面：负责任务生命周期管理（提交、恢复、查询），不承载图编排。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from qingchuan_agent.agents.runtime import AgentRuntime, get_agent_runtime
from qingchuan_agent.constants import TaskStatus
from qingchuan_agent.core.config import settings
from qingchuan_agent.core.exceptions import NotFoundError, ValidationError
from qingchuan_agent.core.logger import logger
from qingchuan_agent.infras.event_bus import EventBus, get_event_bus
from qingchuan_agent.infras.task_stream import TaskStreamQueue, get_task_queue
from qingchuan_agent.models.entities.agent_event import AgentEvent
from qingchuan_agent.models.entities.agent_task import AgentTask
from qingchuan_agent.repositories.agent_event_repository import AgentEventRepository
from qingchuan_agent.repositories.agent_task_repository import AgentTaskRepository
from qingchuan_agent.services.task_execution import (
    invoke_and_finalize,
    resume_and_finalize,
)


class AgentTaskService:
    """Agent 任务服务：任务全生命周期管理（提交 / 恢复 / 查询 / 事件查询）。

    依赖（runtime / event_bus / queue）通过构造函数注入，默认走进程级工厂单例；
    测试或多实现切换时可传入 Mock/替身，不再硬绑全局状态。
    """

    def __init__(
        self,
        session: Session,
        runtime: AgentRuntime | None = None,
        event_bus: EventBus | None = None,
        queue: TaskStreamQueue | None = None,
    ) -> None:
        self._session = session
        self._task_repo = AgentTaskRepository(session)
        self._event_repo = AgentEventRepository(session)
        self._runtime: AgentRuntime = runtime or get_agent_runtime()
        self._event_bus: EventBus = event_bus or get_event_bus()
        # queue 缺省走全局单例（Redis 可用时即异步执行；不可用返回 None 走同步回退）
        self._queue: TaskStreamQueue | None = queue or get_task_queue()

    @property
    def _queue_enabled(self) -> bool:
        """任务队列是否启用（Redis 可用 + 队列已装配）。"""
        return self._queue is not None

    # ----------------------------------------------------------
    # 任务提交
    # ----------------------------------------------------------

    async def submit_task(
        self,
        task_type: str | None,
        payload: dict[str, Any],
        timeout_at: datetime | None = None,
    ) -> AgentTask:
        """提交一个 Agent 任务（Redis 可用时异步入队，接口立即返回）。

        Args:
            task_type: 任务类型（AgentType.mark，如 "customer_service"）；可为 None，
                此时由顶层 RouteResolver 按 payload 自然语言动态路由（hybrid）。
            payload: 任务入参（由各 Agent 自定义结构，按最终路由到的 Agent 选用对应字段）
            timeout_at: 超时时间点（缺省按配置 agent.task_timeout_seconds）

        Returns:
            Redis 可用：已落库入队的 AgentTask（status=running，worker 异步执行后回写）；
            Redis 不可用：同步执行并回写结果后的 AgentTask（开发降级路径）。

        事件双写契约：编排产生的事件同时「落库留痕 + publish 事件总线」，
        publish 失败不影响主流程（仅记日志），总线作为 Agent 间协作广播通道。
        """
        # 1. 显式任务类型校验：传了就必须已注册；留空放行，交顶层 RouteResolver 动态路由
        from qingchuan_agent.agents.registry import agent_registry

        if task_type and not agent_registry.has(task_type):
            raise ValidationError(f"任务类型未注册 Agent：{task_type}")

        # 2. 落库 running（先持久化，获取任务 ID 作为审计主键）。
        #    task_type 非空列不可空，动态路由任务先用 "auto" 占位，
        #    实际派发 Agent 回写 assignee_agent。thread_id 入队前预生成，
        #    供 resume 校验与 checkpoint 定位使用。
        task = AgentTask(
            task_type=task_type or "auto",
            payload=payload,
            status=TaskStatus.RUNNING.mark,
            max_retries=settings.agent.task_max_retries,
            timeout_at=timeout_at
            or datetime.now(UTC) + timedelta(seconds=settings.agent.task_timeout_seconds),
        )
        self._task_repo.add(task)
        self._task_repo.commit()
        thread_id = f"task:{task.id}"
        task.thread_id = thread_id
        logger.info(f"[TaskService] 任务已落库：id={task.id} type={task_type}")

        # 3. 派发执行：Redis 可用 → 入队异步执行；不可用 → 线程池同步回退
        if self._queue_enabled:
            await self._queue.enqueue(
                {
                    "action": "submit",
                    "task_id": task.id,
                    "task_type": task_type or "auto",
                    "thread_id": thread_id,
                    "payload": payload,
                }
            )
            self._task_repo.commit()
            logger.info(f"[TaskService] 任务已入队：id={task.id}（异步执行）")
            return task

        logger.info(f"[TaskService] Redis 不可用，任务同步执行（降级）：id={task.id}")
        await invoke_and_finalize(
            runtime=self._runtime,
            task_repo=self._task_repo,
            event_repo=self._event_repo,
            event_bus=self._event_bus,
            task=task,
            task_type=task_type,
            payload=payload,
            thread_id=thread_id,
        )
        self._task_repo.commit()
        return task

    # ----------------------------------------------------------
    # 任务查询
    # ----------------------------------------------------------

    def get_task(self, task_id: int) -> AgentTask:
        task = self._task_repo.get(task_id)
        if task is None:
            raise NotFoundError(f"任务不存在：{task_id}")
        return task

    def list_tasks(
        self,
        status: str | None = None,
        task_type: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[AgentTask], int]:
        offset = (page - 1) * page_size
        if status:
            items = self._task_repo.list_by_status(status, offset=offset, limit=page_size)
            total = self._task_repo.count_by_status(status)
        elif task_type:
            items = self._task_repo.list_by_task_type(task_type, offset=offset, limit=page_size)
            total = self._task_repo.count(AgentTask.task_type == task_type)
        else:
            items = self._task_repo.list(
                order_by=self._task_repo.model_class.id.desc(), offset=offset, limit=page_size
            )
            total = self._task_repo.count()
        return items, total

    # ----------------------------------------------------------
    # 人工接管（interrupt → resume）
    # ----------------------------------------------------------

    async def resume_task(
        self,
        task_id: int,
        decision: str,
        remark: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> AgentTask:
        """恢复被 interrupt 暂停的任务（人工决策 approve/reject/adjust）。

        恢复后同样执行事件双写（人工决策产生的后续事件落库 + 广播）。
        Redis 可用时入队由 worker 续跑；不可用时同步执行回退。
        """
        task = self.get_task(task_id)
        if not task.thread_id:
            raise ValidationError("任务无线程 ID，无法恢复（可能未执行或已完成）")
        from qingchuan_agent.constants import HumanDecision

        valid_decisions = [item.mark for item in HumanDecision]
        if decision not in valid_decisions:
            raise ValidationError(
                f"非法人工决策：{decision!r}（可选：{', '.join(valid_decisions)}）"
            )
        update = {"decision": decision, "remark": remark, "extra": extra or {}}

        if self._queue_enabled:
            task.status = TaskStatus.RUNNING.mark
            await self._queue.enqueue(
                {
                    "action": "resume",
                    "task_id": task.id,
                    "thread_id": task.thread_id,
                    "decision": decision,
                    "remark": remark or "",
                    "extra": extra or {},
                }
            )
            self._task_repo.commit()
            logger.info(f"[TaskService] 人工接管已入队：id={task.id} decision={decision}")
            return task

        logger.info(f"[TaskService] Redis 不可用，人工接管同步执行（降级）：id={task.id}")
        await resume_and_finalize(
            runtime=self._runtime,
            task_repo=self._task_repo,
            event_repo=self._event_repo,
            event_bus=self._event_bus,
            task=task,
            update=update,
        )
        self._task_repo.commit()
        return task

    # ----------------------------------------------------------
    # 事件查询
    # ----------------------------------------------------------

    def list_events(
        self,
        event_type: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[AgentEvent], int]:
        offset = (page - 1) * page_size
        if event_type:
            items = self._event_repo.list_by_type(event_type, offset=offset, limit=page_size)
            total = self._event_repo.count(AgentEvent.event_type == event_type)
        else:
            items = self._event_repo.list_recent(offset=offset, limit=page_size)
            total = self._event_repo.count()
        return items, total

    def get_event(self, event_id: int) -> AgentEvent:
        """按 ID 取单条协作事件（事件详情 / 审计面板），不存在抛 404。"""
        event = self._event_repo.get(event_id)
        if event is None:
            raise NotFoundError(f"协作事件不存在：{event_id}")
        return event


__all__ = ["AgentTaskService"]
