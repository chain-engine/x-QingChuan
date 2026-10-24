"""问答（客服）Agent（晴川 x-QingChuan，agents/customer_service）。

由早期 RAG 问答 Agent 更名而来：agent_type=customer_service，
task_type 同步使用新 mark。职责：检索人社 / 社保知识库并生成回答。
"""

from __future__ import annotations

from langgraph.graph.state import CompiledStateGraph

from qingchuan_agent.agents.base import BaseAgent
from qingchuan_agent.agents.customer_service.graph import build_customer_service_graph
from qingchuan_agent.constants import AgentType


class CustomerServiceAgent(BaseAgent):
    """问答（客服）Agent：检索人社 / 社保资料并回答。"""

    agent_type: AgentType = AgentType.CUSTOMER_SERVICE
    name: str = "问答（客服）Agent"
    description: str = "RAG 问答客服：检索人社 / 社保知识库并生成回答"
    routing_hint: str = "用户咨询人社 / 社保 / 养老 / 医保 / 社保卡等政策问题时使用（问答客服）"

    def build(self) -> CompiledStateGraph:
        """构建问答（客服）Agent 子图。"""
        return build_customer_service_graph()


__all__ = ["CustomerServiceAgent"]
