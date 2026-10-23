"""数据分析 Agent 子图（晴川 x-QingChuan，agents/data_analysis）。

子图拓扑：START → collect（取数）→ analyze（分析）→ report（报告）→ END。
骨架约定：图结构稳定，接入真实业务只需替换节点内部实现。
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from qingchuan_agent.agents.data_analysis.nodes import analyze_node, collect_node, report_node
from qingchuan_agent.agents.state import AgentTaskState


def build_data_analysis_graph() -> CompiledStateGraph:
    """构建数据分析 Agent 子图（取数 → 分析 → 报告）。"""
    graph = StateGraph(AgentTaskState)
    graph.add_node("collect", collect_node)
    graph.add_node("analyze", analyze_node)
    graph.add_node("report", report_node)
    graph.add_edge(START, "collect")
    graph.add_edge("collect", "analyze")
    graph.add_edge("analyze", "report")
    graph.add_edge("report", END)
    return graph.compile()


__all__ = ["build_data_analysis_graph"]
