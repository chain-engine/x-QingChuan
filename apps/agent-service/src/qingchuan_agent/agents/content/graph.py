"""内容创作 Agent 子图（晴川 x-QingChuan，agents/content）。

子图拓扑：START → plan（选题策划）→ generate（内容生成）→ review（审核）→ END。
骨架约定：图结构稳定，接入真实业务只需替换节点内部实现。
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from qingchuan_agent.agents.content.nodes import generate_node, plan_node, review_node
from qingchuan_agent.agents.state import AgentTaskState


def build_content_graph() -> CompiledStateGraph:
    """构建内容创作 Agent 子图（选题 → 生成 → 审核）。"""
    graph = StateGraph(AgentTaskState)
    graph.add_node("plan", plan_node)
    graph.add_node("generate", generate_node)
    graph.add_node("review", review_node)
    graph.add_edge(START, "plan")
    graph.add_edge("plan", "generate")
    graph.add_edge("generate", "review")
    graph.add_edge("review", END)
    return graph.compile()


__all__ = ["build_content_graph"]
