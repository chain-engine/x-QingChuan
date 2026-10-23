"""数据监控 Agent 子图（晴川 x-QingChuan，agents/data_monitor）。

子图拓扑：START → query（指标查询）→ evaluate（阈值判定）→ notify（通知）→ END。
骨架约定：图结构稳定，接入真实业务只需替换节点内部实现。
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from qingchuan_agent.agents.data_monitor.nodes import evaluate_node, notify_node, query_node
from qingchuan_agent.agents.state import AgentTaskState


def build_data_monitor_graph() -> CompiledStateGraph:
    """构建数据监控 Agent 子图（查询 → 判定 → 通知）。"""
    graph = StateGraph(AgentTaskState)
    graph.add_node("query", query_node)
    graph.add_node("evaluate", evaluate_node)
    graph.add_node("notify", notify_node)
    graph.add_edge(START, "query")
    graph.add_edge("query", "evaluate")
    graph.add_edge("evaluate", "notify")
    graph.add_edge("notify", END)
    return graph.compile()


__all__ = ["build_data_monitor_graph"]
