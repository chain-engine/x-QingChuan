"""安全 Agent 子图（晴川 x-QingChuan，agents/security）。

子图拓扑：START → collect（采集）→ analyze（风险分析）→ alert（告警）→ END。
骨架约定：图结构稳定，接入真实业务只需替换节点内部实现。
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from qingchuan_agent.agents.security.nodes import alert_node, analyze_node, collect_node
from qingchuan_agent.agents.state import AgentTaskState


def build_security_graph() -> CompiledStateGraph:
    """构建安全 Agent 子图（采集 → 风险分析 → 告警）。"""
    graph = StateGraph(AgentTaskState)
    graph.add_node("collect", collect_node)
    graph.add_node("analyze", analyze_node)
    graph.add_node("alert", alert_node)
    graph.add_edge(START, "collect")
    graph.add_edge("collect", "analyze")
    graph.add_edge("analyze", "alert")
    graph.add_edge("alert", END)
    return graph.compile()


__all__ = ["build_security_graph"]
