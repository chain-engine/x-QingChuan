"""数据监控 Agent（晴川 x-QingChuan，agents/data_monitor）。

职责：数据监控工作流（指标查询 → 阈值判定 / 异常识别 → 通知推送）。
骨架阶段：子图可编译可运行，业务步骤 todo 占位。
"""

from __future__ import annotations

from langgraph.graph.state import CompiledStateGraph

from qingchuan_agent.agents.base import BaseAgent
from qingchuan_agent.agents.data_monitor.graph import build_data_monitor_graph
from qingchuan_agent.constants import AgentType


class DataMonitorAgent(BaseAgent):
    """数据监控 Agent：指标查询 → 阈值判定 → 通知推送。"""

    agent_type: AgentType = AgentType.DATA_MONITOR
    name: str = "数据监控 Agent"
    description: str = "数据监控工作流：指标查询、异常判定与通知推送"
    routing_hint: str = "需要监控指标、识别异常并推送通知时使用（数据监控）"

    def build(self) -> CompiledStateGraph:
        """构建数据监控 Agent 子图。"""
        return build_data_monitor_graph()


__all__ = ["DataMonitorAgent"]
