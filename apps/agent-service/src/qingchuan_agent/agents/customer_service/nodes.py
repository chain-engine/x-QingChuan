"""问答（客服）Agent 节点（晴川 x-QingChuan，agents/customer_service）。

answer 节点 = 检索（MCP → rag-service）→ LLM 答案生成。
链路已闭环：
    answer → tool_registry.invoke("rag.retrieve")
        → RagMCPClient（qingchuan_common.mcp MCPClient）
        → rag-service /mcp（streamable HTTP）retrieve_docs
    → 命中片段组装上下文 → LLM 生成答案（有 key 真实生成，无 key Mock 并标注）

空库 / 空命中分支：不报错，返回明确文案（与 rag-service 空库语义一致）。
"""

from __future__ import annotations

from typing import Any

from qingchuan_agent.agents.common import build_context, call_llm, extract_query, get_int
from qingchuan_agent.agents.customer_service.prompts import SYSTEM_PROMPT
from qingchuan_agent.agents.state import AgentTaskState
from qingchuan_agent.agents.tools.registry import tool_registry
from qingchuan_agent.constants import TaskStatus
from qingchuan_agent.core.logger import logger


def answer_node(state: AgentTaskState) -> dict[str, Any]:
    """RAG 问答节点：检索（MCP → rag-service）→ LLM 生成答案。"""
    payload = state.get("payload") or {}
    query = extract_query(payload)
    if not query:
        return {
            "status": TaskStatus.FAILED.mark,
            "error": "缺少查询文本：payload 需包含 query / message / question 之一",
        }

    top_k = get_int(payload, "top_k", default=5)
    try:
        # 1. MCP 检索：经工具注册中心调用 rag.retrieve → rag-service /mcp
        docs = tool_registry.invoke("rag.retrieve", query=query, top_k=top_k)
        logger.info(f"[CustomerService] MCP 检索完成：query={query[:60]} hits={len(docs)}")

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
        context = build_context(docs)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"参考资料：\n{context}\n\n问题：{query}\n\n请回答：",
            },
        ]
        answer = call_llm(messages)
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
        logger.exception(f"[CustomerService] RAG 问答失败：{exc}")
        return {
            "status": TaskStatus.FAILED.mark,
            "error": str(exc),
            "result": None,
        }


__all__ = ["answer_node"]
