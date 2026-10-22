#!/usr/bin/env python3
"""Agent 统一运行时（晴川 x-QingChuan，对齐北辰形态）。

负责：
    1. 顶层编排图（调度中枢）的构建与编译
    2. checkpointer 装配（memory / redis）
    3. 任务执行 invoke 与人工接管 resume（interrupt 断点续跑）
    4. 执行上下文（thread_id）管理

标准调用链（LangGraph + LangChain 配合）：
    AgentRuntime.invoke_task() ──▶ 顶层编排图（orchestrator）
        └── route 节点（注册表路由）
        └── subagent 节点（调用业务子图）
            └── 子图节点内部：ChatPromptTemplate + ChatOpenAI（LangChain，待接入）
        └── aggregate 节点（聚合结果）
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from qingchuan_agent.agents.registry import AgentRegistry, agent_registry
from qingchuan_agent.constants import AgentRunStatus, TaskStatus
from qingchuan_agent.core.config import get_settings
from qingchuan_agent.core.logger import logger

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph


class AgentRuntime:
    """Agent 运行时：编排图构建 + 检查点 + 执行 / 恢复。"""

    def __init__(self, registry: AgentRegistry | None = None) -> None:
        self._registry: AgentRegistry = registry or agent_registry
        self._orchestrator: CompiledStateGraph | None = None
        self._checkpointer: Any | None = None

    # ----------------------------------------------------------
    # checkpointer
    # ----------------------------------------------------------

    def _get_checkpointer(self) -> Any | None:
        """按配置装配检查点：
        - memory：进程内内存（开发期，重启丢状态）
        - redis：LangGraph RedisSaver（与事件总线共用同一 Redis 实例）；
          Redis 未启用或连接不可用时回退 memory 并告警（不阻断业务）
        """
        if self._checkpointer is not None:
            return self._checkpointer
        settings = get_settings()
        if settings.agent.checkpoint == "redis":
            from qingchuan_agent.infras.redis_client import (
                get_sync_redis_client,
                redis_available,
            )

            if settings.redis.enabled and redis_available():
                from langgraph.checkpoint.redis import RedisSaver

                try:
                    saver = RedisSaver(redis_client=get_sync_redis_client())
                    saver.setup()  # 建 checkpoint 索引（幂等）
                    self._checkpointer = saver
                    logger.info(
                        "AgentRuntime checkpointer：RedisSaver"
                        "（多副本共享断点，人工接管可跨实例恢复）"
                    )
                    return self._checkpointer
                except Exception as exc:
                    logger.warning(f"RedisSaver 初始化失败（{exc}），回退 MemorySaver")
            else:
                logger.warning(
                    "agent.checkpoint=redis 但 Redis 未启用/不可用，回退 MemorySaver（重启即失）"
                )
        from langgraph.checkpoint.memory import MemorySaver

        self._checkpointer = MemorySaver()
        logger.info("AgentRuntime checkpointer：MemorySaver（骨架阶段，重启即失）")
        return self._checkpointer

    # ----------------------------------------------------------
    # 编排图
    # ----------------------------------------------------------

    def build_orchestrator(self) -> CompiledStateGraph:
        """构建顶层调度中枢编排图（懒加载 + 缓存）。"""
        if self._orchestrator is None:
            from qingchuan_agent.agents.orchestrator import build_orchestrator_graph

            self._orchestrator = build_orchestrator_graph(
                self._registry, checkpointer=self._get_checkpointer()
            )
            logger.info("顶层编排图（Orchestrator）构建完成")
        return self._orchestrator

    # ----------------------------------------------------------
    # 执行
    # ----------------------------------------------------------

    def invoke_task(
        self,
        task_type: str,
        payload: dict[str, Any],
        thread_id: str | None = None,
        task_id: int | None = None,
    ) -> dict[str, Any]:
        """提交并执行一个 Agent 任务（同步执行入口）。

        Args:
            task_type: 任务类型（如 "agent_a"）
            payload: 任务入参
            thread_id: LangGraph 线程 ID（断点续跑定位；缺省自动生成）
            task_id: 落库任务 ID（回写审计）

        Returns:
            编排图最终状态（含 status / result / events）
        """
        import uuid

        orchestrator = self.build_orchestrator()
        thread = thread_id or f"{task_type}:{task_id or 'anon'}:{uuid.uuid4().hex[:8]}"
        initial_state: dict[str, Any] = {
            "task_id": task_id or 0,
            "task_type": task_type,
            "payload": payload,
            "target_agent": None,
            # 字符串值：checkpoint 只序列化基础类型（枚举实例未来会被阻断）
            "status": TaskStatus.RUNNING.mark,
            "result": None,
            "error": None,
            "events": [],
        }
        config = {"configurable": {"thread_id": thread}}
        logger.info(f"[Runtime] invoke task={task_type} thread={thread}")
        try:
            final_state = orchestrator.invoke(initial_state, config=config)
            # 人工接管识别：子图 interrupt() 后 LangGraph 在状态中注入 __interrupt__。
            # 此时任务处于"等待人工"而非失败/完成，需：
            #   1) 状态置 WAITING_HUMAN（管理后台可区分"执行中"与"等待人工"）
            #   2) 剔除 __interrupt__（Interrupt 对象不可 JSON 序列化，避免落库失败）
            #   3) 把人工接管上下文写入 result（可序列化，供人工面板展示）
            if "__interrupt__" in final_state:
                interrupts = final_state.pop("__interrupt__")
                final_state["status"] = TaskStatus.WAITING_HUMAN.mark
                if final_state.get("result") is None:
                    first = interrupts[0] if isinstance(interrupts, (list, tuple)) else interrupts
                    interrupt_ctx = getattr(first, "value", None) or {}
                    final_state["result"] = {"interrupt": interrupt_ctx}
                logger.info(f"[Runtime] task interrupted thread={thread} → waiting_human")
            else:
                logger.info(
                    f"[Runtime] task done thread={thread} status={final_state.get('status')}"
                )
            return final_state
        except Exception as exc:
            logger.exception(f"[Runtime] task failed thread={thread}: {exc}")
            return {
                **initial_state,
                "status": TaskStatus.FAILED.mark,
                "error": str(exc),
            }

    def resume_task(self, thread_id: str, update: dict[str, Any]) -> dict[str, Any]:
        """人工接管后恢复执行（LangGraph interrupt/resume）。

        Args:
            thread_id: 原任务线程 ID
            update: 人工决策载荷（approve/reject/adjust + 备注）

        Returns:
            恢复后的最终状态
        """
        orchestrator = self.build_orchestrator()
        config = {"configurable": {"thread_id": thread_id}}
        logger.info(f"[Runtime] resume thread={thread_id} update={update}")
        try:
            # LangGraph 约定：用 Command(resume=...) 传递人工决策，
            # 框架从 checkpoint 定位中断点并继续执行（断点续跑）。
            from langgraph.types import Command

            final_state = orchestrator.invoke(Command(resume=update), config=config)
            return final_state
        except Exception as exc:
            logger.exception(f"[Runtime] resume failed thread={thread_id}: {exc}")
            return {"status": TaskStatus.FAILED.mark, "error": str(exc)}

    def get_run_status(self) -> dict[str, str]:
        """运行状态快照（管理后台可观测面板用）。"""
        return {
            "orchestrator_ready": str(self._orchestrator is not None),
            "checkpointer": get_settings().agent.checkpoint,
            "run_status": AgentRunStatus.IDLE,
        }


# 全局单例（FastAPI 依赖注入 / service 层统一使用）
_runtime: AgentRuntime | None = None


def get_agent_runtime() -> AgentRuntime:
    """获取全局 AgentRuntime 单例。"""
    global _runtime
    if _runtime is None:
        _runtime = AgentRuntime()
    return _runtime


__all__ = ["AgentRuntime", "get_agent_runtime"]
