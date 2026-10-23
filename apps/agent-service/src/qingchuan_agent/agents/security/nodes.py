"""安全 Agent 节点（晴川 x-QingChuan，agents/security）。

骨架阶段：业务节点全部 todo 占位（复用 common.todo_node），
保证子图可编译、可跑通；接入真实业务时替换为真实节点函数。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from qingchuan_agent.agents.common import todo_node
from qingchuan_agent.agents.state import AgentTaskState

# 节点函数（占位）：与 graph.py 的节点名一一对应
collect_node: Callable[[AgentTaskState], dict[str, Any]] = todo_node("日志 / 事件采集")
analyze_node: Callable[[AgentTaskState], dict[str, Any]] = todo_node("风险分析判定")
alert_node: Callable[[AgentTaskState], dict[str, Any]] = todo_node("告警处置")

__all__ = ["alert_node", "analyze_node", "collect_node"]
