#!/usr/bin/env python3
"""Agent A：RAG 问答 Agent（晴川 x-QingChuan，骨架占位）。

子图结构：占位节点直接返回成功结果；接入真实业务时把节点函数内部
换成「工具 rag.retrieve（MCP 客户端 → rag-service）→ LLM 答案生成」
即可，图结构保持不变（对齐 BaseAgent 构建契约）。
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from qingchuan_agent.agents.base import BaseAgent
from qingchuan_agent.agents.registry import AgentSpec, agent_registry
from qingchuan_agent.agents.state import AgentTaskState
from qingchuan_agent.constants import AgentType, TaskStatus
from qingchuan_agent.core.logger import logger


def _answer_node(state: AgentTaskState) -> dict[str, Any]:
    """占位回答节点。

    TODO: 经 tools 的 rag.retrieve（MCP 客户端 → rag-service）检索人社 /
          社保资料，再交给 LLM 生成答案；检索失败按下游 Agent 约定返回失败。
    """
    payload = state.get("payload") or {}
    logger.info(f"[AgentA] 收到任务：{payload}")
    return {
        "status": TaskStatus.SUCCESS.mark,
        "result": {"message": "占位回答：待接入 rag-service MCP 检索工具"},
    }


class AgentA(BaseAgent):
    """RAG 问答 Agent（占位）：检索人社 / 社保资料并回答。"""

    agent_type: AgentType = AgentType.AGENT_A
    name: str = "Agent A"
    description: str = "RAG 问答：检索人社 / 社保资料并回答"

    def build(self) -> CompiledStateGraph:
        """构建 Agent A 子图（占位节点 → 编译）。"""
        graph = StateGraph(AgentTaskState)
        graph.add_node("answer", _answer_node)
        graph.add_edge(START, "answer")
        graph.add_edge("answer", END)
        return graph.compile()


agent_registry.register(AgentSpec(agent=AgentA()))
