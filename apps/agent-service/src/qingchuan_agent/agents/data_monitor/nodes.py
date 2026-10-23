"""数据监控 Agent 节点（晴川 x-QingChuan，agents/data_monitor）。

骨架阶段：业务节点全部 todo 占位（复用 common.todo_node），
保证子图可编译、可跑通；接入真实业务时替换为真实节点函数。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from qingchuan_agent.agents.common import todo_node
from qingchuan_agent.agents.state import AgentTaskState

# 节点函数（占位）：与 graph.py 的节点名一一对应
query_node: Callable[[AgentTaskState], dict[str, Any]] = todo_node("监控指标查询")
evaluate_node: Callable[[AgentTaskState], dict[str, Any]] = todo_node("阈值判定 / 异常识别")
notify_node: Callable[[AgentTaskState], dict[str, Any]] = todo_node("监控通知推送")

__all__ = ["evaluate_node", "notify_node", "query_node"]
