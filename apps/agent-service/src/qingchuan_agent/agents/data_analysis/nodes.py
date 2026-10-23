"""数据分析 Agent 节点（晴川 x-QingChuan，agents/data_analysis）。

骨架阶段：业务节点全部 todo 占位（复用 common.todo_node），
保证子图可编译、可跑通；接入真实业务时替换为真实节点函数。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from qingchuan_agent.agents.common import todo_node
from qingchuan_agent.agents.state import AgentTaskState

# 节点函数（占位）：与 graph.py 的节点名一一对应
collect_node: Callable[[AgentTaskState], dict[str, Any]] = todo_node("数据取数")
analyze_node: Callable[[AgentTaskState], dict[str, Any]] = todo_node("数据计算与分析")
report_node: Callable[[AgentTaskState], dict[str, Any]] = todo_node("分析报告生成")

__all__ = ["analyze_node", "collect_node", "report_node"]
