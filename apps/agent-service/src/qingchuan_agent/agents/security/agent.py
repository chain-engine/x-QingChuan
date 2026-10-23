"""安全 Agent（晴川 x-QingChuan，agents/security）。

职责：安全分析与处置工作流（日志 / 事件采集 → 风险分析 → 告警处置）。
骨架阶段：子图可编译可运行，业务步骤 todo 占位。
"""

from __future__ import annotations

from langgraph.graph.state import CompiledStateGraph

from qingchuan_agent.agents.base import BaseAgent
from qingchuan_agent.agents.security.graph import build_security_graph
from qingchuan_agent.constants import AgentType


class SecurityAgent(BaseAgent):
    """安全 Agent：日志 / 事件采集 → 风险分析 → 告警处置。"""

    agent_type: AgentType = AgentType.SECURITY
    name: str = "安全 Agent"
    description: str = "安全分析与处置工作流：采集、风险分析与告警"
    routing_hint: str = "涉及安全分析、日志审计、风险告警、异常检测时使用（安全）"

    def build(self) -> CompiledStateGraph:
        """构建安全 Agent 子图。"""
        return build_security_graph()


__all__ = ["SecurityAgent"]
