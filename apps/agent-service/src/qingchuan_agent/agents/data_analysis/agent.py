"""数据分析 Agent（晴川 x-QingChuan，agents/data_analysis）。

职责：数据分析工作流（取数 → 分析计算 → 报告生成）。
骨架阶段：子图可编译可运行，业务步骤 todo 占位。
"""

from __future__ import annotations

from langgraph.graph.state import CompiledStateGraph

from qingchuan_agent.agents.base import BaseAgent
from qingchuan_agent.agents.data_analysis.graph import build_data_analysis_graph
from qingchuan_agent.constants import AgentType


class DataAnalysisAgent(BaseAgent):
    """数据分析 Agent：取数 → 分析计算 → 报告生成。"""

    agent_type: AgentType = AgentType.DATA_ANALYSIS
    name: str = "数据分析 Agent"
    description: str = "数据分析工作流：取数、计算分析与报告生成"
    routing_hint: str = "需要对数据进行取数、统计、分析并产出结论 / 报告时使用（数据分析）"

    def build(self) -> CompiledStateGraph:
        """构建数据分析 Agent 子图。"""
        return build_data_analysis_graph()


__all__ = ["DataAnalysisAgent"]
