"""问答（客服）Agent 子图（晴川 x-QingChuan，agents/customer_service）。

子图拓扑：START → answer（检索 + 生成）→ END。
骨架约定：图结构稳定，接入真实业务只需替换节点内部实现。
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from qingchuan_agent.agents.customer_service.nodes import answer_node
from qingchuan_agent.agents.state import AgentTaskState


def build_customer_service_graph() -> CompiledStateGraph:
    """构建问答（客服）Agent 子图（answer 节点 → 编译）。"""
    graph = StateGraph(AgentTaskState)
    graph.add_node("answer", answer_node)
    graph.add_edge(START, "answer")
    graph.add_edge("answer", END)
    return graph.compile()


__all__ = ["build_customer_service_graph"]
