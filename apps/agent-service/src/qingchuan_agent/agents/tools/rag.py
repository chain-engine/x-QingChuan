#!/usr/bin/env python3
"""RAG 工具定义（晴川 x-QingChuan）。

把 rag-service 的 MCP 工具（retrieve_docs / rag_query）注册为只读工具，
供 Agent 节点编排使用：

    - rag.retrieve：语义检索人社 / 社保资料（MCP → rag-service）
    - rag.query：   基于知识库生成完整回答（MCP → rag-service）

调用链：Agent 节点 → tool_registry.invoke → RagMCPClient → MCPClient
（qingchuan_common.mcp，Streamable HTTP）→ rag-service /mcp。
本模块在导入时完成注册（由 agents/tools/__init__.py 导入触发）。
"""

from __future__ import annotations

from typing import Any

from qingchuan_domain.schemas.retrieval import RetrievedChunk

from qingchuan_agent.agents.tools.registry import ToolSpec, tool_registry
from qingchuan_agent.constants import ToolPermissionLevel
from qingchuan_agent.infras.rag_mcp import get_rag_mcp_client


def _retrieve(
    query: str,
    top_k: int = 5,
    similarity_threshold: float = 0.7,
    use_mmr: bool = False,
    mmr_lambda: float = 0.5,
    metadata_filter: dict[str, Any] | None = None,
) -> list[RetrievedChunk]:
    """语义检索人社 / 社保资料（MCP → rag-service retrieve_docs，只读，返回领域契约）。"""
    return get_rag_mcp_client().retrieve_docs(
        query=query,
        top_k=top_k,
        similarity_threshold=similarity_threshold,
        use_mmr=use_mmr,
        mmr_lambda=mmr_lambda,
        metadata_filter=metadata_filter,
    )


def _rag_query(
    query: str,
    top_k: int = 5,
    similarity_threshold: float = 0.7,
    use_mmr: bool = False,
    mmr_lambda: float = 0.5,
    metadata_filter: dict[str, Any] | None = None,
    provider: str | None = None,
    temperature: float | None = 0.7,
    max_tokens: int | None = 2048,
) -> dict[str, Any]:
    """基于知识库生成完整回答（MCP → rag-service rag_query，只读）。"""
    return get_rag_mcp_client().rag_query(
        query=query,
        top_k=top_k,
        similarity_threshold=similarity_threshold,
        use_mmr=use_mmr,
        mmr_lambda=mmr_lambda,
        metadata_filter=metadata_filter,
        provider=provider,
        temperature=temperature,
        max_tokens=max_tokens,
    )


tool_registry.register(
    ToolSpec(
        name="rag.retrieve",
        description="语义检索人社 / 社保资料，返回 Top-K 相关片段（MCP → rag-service）",
        func=_retrieve,
        permission_level=ToolPermissionLevel.READ,
    )
)

tool_registry.register(
    ToolSpec(
        name="rag.query",
        description="基于知识库生成完整回答，返回答案与引用片段（MCP → rag-service）",
        func=_rag_query,
        permission_level=ToolPermissionLevel.READ,
    )
)

__all__ = ["tool_registry"]
