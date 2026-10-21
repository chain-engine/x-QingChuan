#!/usr/bin/env python3
"""rag-service MCP 客户端（agent → rag 的 MCP 调用闭环，晴川 x-QingChuan）。

职责：
    - 把 qingchuan_common.mcp 的通用 MCP 客户端绑定到 rag-service 工具契约
      （retrieve_docs / rag_query），收敛默认参数与返回结构；
    - MCP 优先（行业主流）：连接 rag-service 的 streamable HTTP /mcp 端点；
    - 提供同步方法供 LangGraph 同步节点 / 工具注册中心直接调用
      （内部 asyncio.run，调用方不得处于事件循环中；编排线程内安全）。

返回契约（对齐共享领域包 qingchuan_domain）：
    retrieve_docs → list[RetrievedChunk]（领域契约，HTTP/MCP 响应结构已在 P0-2 归并）
    rag_query     → {answer, retrieved_docs: list[RetrievedChunk], provider, model, tokens_used}
"""

from __future__ import annotations

from typing import Any

from qingchuan_common.mcp import MCPClient, MCPClientError
from qingchuan_domain.schemas.retrieval import RetrievedChunk

from qingchuan_agent.core.config import settings
from qingchuan_agent.core.logger import logger


def _to_retrieved_chunks(data: Any) -> list[RetrievedChunk]:
    """把 MCP 返回的原始片段转换为领域契约 RetrievedChunk 列表。

    兼容服务端两种形态：{"items": [...]}（稳定外壳，当前服务端）与裸 list。
    """
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        data = data["items"]
    if not isinstance(data, list):
        return []
    chunks: list[RetrievedChunk] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            chunks.append(RetrievedChunk.model_validate(item))
        except Exception:
            logger.warning(f"[RagMCP] 忽略无法解析的检索片段：{str(item)[:120]}")
    return chunks


class RagMCPClient:
    """rag-service 的 MCP 工具客户端（retrieve_docs / rag_query）。"""

    def __init__(self, mcp_url: str | None = None, timeout: float | None = None) -> None:
        rag_cfg = settings.rag
        self._client = MCPClient(
            url=mcp_url or rag_cfg.mcp_url,
            timeout=timeout or rag_cfg.mcp_timeout_seconds,
        )
        logger.info(f"[RagMCP] MCP 客户端就绪：{self._client.url}")

    # ------------------------------------------------------------------
    # 工具契约（与 rag-service mcp_server/tools.py 对齐）
    # ------------------------------------------------------------------

    def retrieve_docs(
        self,
        query: str,
        top_k: int = 5,
        similarity_threshold: float = 0.7,
        use_mmr: bool = False,
        mmr_lambda: float = 0.5,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[RetrievedChunk]:
        """检索知识库中最相关的文档片段（仅检索，不生成）。

        Returns:
            领域契约片段列表（RetrievedChunk：chunk_id/document_id/source/text/score/metadata）
        """
        result = self._client.call_tool_sync(
            "retrieve_docs",
            {
                "query": query,
                "top_k": top_k,
                "similarity_threshold": similarity_threshold,
                "use_mmr": use_mmr,
                "mmr_lambda": mmr_lambda,
                "metadata_filter": metadata_filter,
            },
        )
        return _to_retrieved_chunks(result.get("data"))

    def rag_query(
        self,
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
        """基于知识库生成完整回答（检索→增强→生成流水线，由 rag-service 完成）。

        Returns:
            {answer, retrieved_docs: list[RetrievedChunk], provider, model, tokens_used}
        """
        result = self._client.call_tool_sync(
            "rag_query",
            {
                "query": query,
                "top_k": top_k,
                "similarity_threshold": similarity_threshold,
                "use_mmr": use_mmr,
                "mmr_lambda": mmr_lambda,
                "metadata_filter": metadata_filter,
                "provider": provider,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )
        data = result.get("data") or {}
        if isinstance(data, dict) and "retrieved_docs" in data:
            data["retrieved_docs"] = _to_retrieved_chunks(data["retrieved_docs"])
        return data

    @property
    def mcp_url(self) -> str:
        return self._client.url


# 全局单例（懒加载：首次调用时按配置构建）
_rag_mcp_client: RagMCPClient | None = None


def get_rag_mcp_client() -> RagMCPClient:
    """获取全局 RagMCPClient 单例。"""
    global _rag_mcp_client
    if _rag_mcp_client is None:
        _rag_mcp_client = RagMCPClient()
    return _rag_mcp_client


__all__ = ["MCPClientError", "RagMCPClient", "RetrievedChunk", "get_rag_mcp_client"]
