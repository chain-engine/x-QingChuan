#!/usr/bin/env python3
"""Agent A：RAG 问答 Agent（晴川 x-QingChuan）。

子图结构：answer 节点 = 检索（MCP → rag-service）→ LLM 答案生成。
链路已闭环：
    agent_a.answer → tool_registry.invoke("rag.retrieve")
        → RagMCPClient（qingchuan_common.mcp MCPClient）
        → rag-service /mcp（streamable HTTP）retrieve_docs
    → 命中片段组装上下文 → LLMProvider 生成答案（有 key 真实生成，无 key Mock 并标注）
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from qingchuan_domain.schemas.retrieval import RetrievedChunk

from qingchuan_agent.agents.base import BaseAgent
from qingchuan_agent.agents.registry import AgentSpec, agent_registry
from qingchuan_agent.agents.state import AgentTaskState
from qingchuan_agent.agents.tools.registry import tool_registry
from qingchuan_agent.constants import AgentType, TaskStatus
from qingchuan_agent.core.logger import logger
from qingchuan_agent.infras.llm import get_llm_provider

# 检索入参（payload 可选字段）
_QUERY_KEYS = ("query", "message", "question")
_SYSTEM_PROMPT = (
    "你是晴川（QingChuan）人社知识助手。请严格依据下方提供的知识片段回答用户问题；"
    "若片段信息不足，明确说明依据片段无法回答，不要编造。"
)


def _extract_query(payload: dict[str, Any]) -> str:
    """从任务 payload 提取查询文本。"""
    for key in _QUERY_KEYS:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _build_context(docs: list[RetrievedChunk]) -> str:
    """把检索片段组装为带序号的上下文文本（领域契约 RetrievedChunk）。"""
    parts = []
    for index, doc in enumerate(docs, start=1):
        text = str(doc.text or "").strip()
        if text:
            parts.append(f"[片段{index}] {text}")
    return "\n\n".join(parts)


def _answer_node(state: AgentTaskState) -> dict[str, Any]:
    """RAG 问答节点：检索（MCP → rag-service）→ LLM 生成答案。"""
    payload = state.get("payload") or {}
    query = _extract_query(payload)
    if not query:
        return {
            "status": TaskStatus.FAILED.mark,
            "error": "缺少查询文本：payload 需包含 query / message / question 之一",
        }

    top_k = int(payload.get("top_k") or 5)
    try:
        # 1. MCP 检索：经工具注册中心调用 rag.retrieve → rag-service /mcp
        docs = tool_registry.invoke("rag.retrieve", query=query, top_k=top_k)
        logger.info(f"[AgentA] MCP 检索完成：query={query[:60]} hits={len(docs)}")

        if not docs:
            return {
                "status": TaskStatus.SUCCESS.mark,
                "result": {
                    "answer": "知识库中未检索到与问题相关的资料。",
                    "retrieved_docs": [],
                    "query": query,
                },
            }

        # 2. LLM 生成：检索片段作为上下文注入
        context = _build_context(docs)
        llm = get_llm_provider()
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"参考资料：\n{context}\n\n问题：{query}\n\n请回答：",
            },
        ]
        answer = llm.chat(messages)
        return {
            "status": TaskStatus.SUCCESS.mark,
            "result": {
                "answer": answer,
                "retrieved_docs": [doc.model_dump(mode="json") for doc in docs],
                "query": query,
                "context_count": len(docs),
            },
        }
    except Exception as exc:
        logger.exception(f"[AgentA] RAG 问答失败：{exc}")
        return {
            "status": TaskStatus.FAILED.mark,
            "error": str(exc),
            "result": None,
        }


class AgentA(BaseAgent):
    """RAG 问答 Agent：检索人社 / 社保资料并回答。"""

    agent_type: AgentType = AgentType.AGENT_A
    name: str = "Agent A"
    description: str = "RAG 问答：检索人社 / 社保资料并回答"

    def build(self) -> CompiledStateGraph:
        """构建 Agent A 子图（answer 节点 → 编译）。"""
        graph = StateGraph(AgentTaskState)
        graph.add_node("answer", _answer_node)
        graph.add_edge(START, "answer")
        graph.add_edge("answer", END)
        return graph.compile()


agent_registry.register(AgentSpec(agent=AgentA()))
