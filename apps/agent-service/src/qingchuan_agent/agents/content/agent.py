"""内容创作 Agent（晴川 x-QingChuan，agents/content）。

职责：面向自媒体 / 内容运营的创作工作流（选题策划 → 内容生成 → 审核）。
骨架阶段：子图可编译可运行，业务步骤 todo 占位。
"""

from __future__ import annotations

from langgraph.graph.state import CompiledStateGraph

from qingchuan_agent.agents.base import BaseAgent
from qingchuan_agent.agents.content.graph import build_content_graph
from qingchuan_agent.constants import AgentType


class ContentCreationAgent(BaseAgent):
    """内容创作 Agent：选题策划 → 内容生成 → 审核。"""

    agent_type: AgentType = AgentType.CONTENT
    name: str = "内容创作 Agent"
    description: str = "内容创作工作流：选题策划、内容生成与审核"
    routing_hint: str = "需要创作 / 撰写 / 策划内容（文章、图文、脚本等）时使用（内容创作）"

    def build(self) -> CompiledStateGraph:
        """构建内容创作 Agent 子图。"""
        return build_content_graph()


__all__ = ["ContentCreationAgent"]
