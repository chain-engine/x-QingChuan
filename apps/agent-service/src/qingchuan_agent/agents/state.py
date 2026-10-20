#!/usr/bin/env python3
"""Agent 编排层共享状态定义（晴川 x-QingChuan，对齐北辰形态）。

状态即 LangGraph 图中流动的数据载体（TypedDict）：
    AgentTaskState —— 任务通用字段（顶层与所有子图共享的合并契约）
    OrchestratorState —— 顶层调度中枢状态（在通用字段上扩展 target_agent）

字段约定：
    task_type / task_id —— 路由与审计
    payload —— 任务入参
    status / result / error —— 执行结果归一化
    events —— 协作事件累计（子图节点追加，顶层聚合后落库）
"""

from __future__ import annotations

from typing import Any, TypedDict


class AgentTaskState(TypedDict, total=False):
    """任务通用状态（顶层与子图共享字段的合并契约）。

    子图内嵌顶层图时，LangGraph 会把子图输出的 dict 与顶层状态做同名键合并；
    因此子图继承本类即可获得 status / result / error / events
    的回传能力，不必重复声明。
    """

    task_id: int
    task_type: str
    payload: dict[str, Any]
    status: str
    result: dict[str, Any] | None
    error: str | None
    events: list[dict[str, Any]]


class OrchestratorState(AgentTaskState):
    """顶层调度中枢状态（调度链路：route → subagent → aggregate）。"""

    target_agent: str | None  # route 节点写入：实际派发目标 Agent
    # 路由决策观测字段（仅审计 / 可观测，子图不声明、不回传，不污染子图状态）
    route_mode: str | None  # 实际采用的路由方式：explicit / llm / fallback
    route_confidence: float | None  # LLM 路由置信度（显式路由为 None）
    route_reason: str | None  # 路由选择理由（LLM 给出或回退说明）
