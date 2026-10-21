#!/usr/bin/env python3
"""MCP 工具原语（Tools）——当前暴露只读检索技能。

注册方式：由 server._register_all 调用 register_tools(server, get_rag_service)，
工具实现经闭包捕获服务获取函数，避免本模块与装配层（server.py）循环依赖。

新增工具约定：在本文件 register_tools 内追加 @server.tool() 函数，
保持"只读 + 复用 services"原则（文档上传 / 删除等写操作继续走 HTTP 管理面）。

操作人：晴川为内部服务，不设应用鉴权，审计操作人统一记为
系统操作（operator=None，审计记录 operator_id 为空）。
"""

from __future__ import annotations

from collections.abc import Callable

from mcp.server.mcpserver import MCPServer

from qingchuan_rag.constants import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_MMR_LAMBDA,
    DEFAULT_SIMILARITY_THRESHOLD,
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_K,
)
from qingchuan_rag.core.exceptions import GenerationError, RetrievalError
from qingchuan_rag.core.logger import logger
from qingchuan_rag.schemas.rag import from_search_results
from qingchuan_rag.services.rag_service import RAGService


def _to_mcp_error(exc: Exception) -> Exception:
    """将底层异常转换为 MCP 客户端可读的错误并记录日志，避免泄漏内部堆栈"""
    if isinstance(exc, (RetrievalError, GenerationError)):
        logger.error(f"MCP tool error: {exc.message}")
        return ValueError(exc.message)
    logger.opt(exception=True).error("MCP tool unhandled error")
    return RuntimeError(f"Internal error: {exc}")


def register_tools(
    server: MCPServer,
    get_rag_service: Callable[[], RAGService],
) -> None:
    """注册 MCP 工具（只读 RAG 能力）。"""

    @server.tool()
    def retrieve_docs(
        query: str,
        top_k: int = DEFAULT_TOP_K,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        use_mmr: bool = False,
        mmr_lambda: float = DEFAULT_MMR_LAMBDA,
        metadata_filter: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """检索与查询最相关的知识片段，返回片段文本、相似度分数与元数据（仅检索，不生成）。

        Args:
            query: 用户查询内容，支持中英文。
            top_k: 返回的相关文档数量。
            similarity_threshold: 相似度阈值，低于该值的文档被过滤。
            use_mmr: 是否使用 MMR 算法增加结果多样性。
            mmr_lambda: MMR 参数，0.0=多样性优先，1.0=相关性优先。
            metadata_filter: 元数据过滤条件，如 {"file_type": "pdf"}。

        Returns:
            稳定结构 {"items": [片段, ...]}，每项含 chunk_id/document_id/text/score/metadata。
        """
        try:
            documents = get_rag_service().retrieve(
                query=query,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
                use_mmr=use_mmr,
                mmr_lambda=mmr_lambda,
                metadata_filter=metadata_filter,
            )
            # 包一层稳定结构 {"items": [...]}：mcp SDK 服务端会把顶层 list 按元素
            # 序列化为多个 text 块，单元素列表会被客户端解析为 dict 造成结构塌缩；
            # 固定 dict 外壳保证客户端按 "items" 稳定取数组。
            return {"items": [doc.model_dump() for doc in from_search_results(documents)]}
        except Exception as exc:  # noqa: BLE001 - 统一转换为 MCP 可读错误
            raise _to_mcp_error(exc) from exc

    @server.tool()
    async def rag_query(
        query: str,
        top_k: int = DEFAULT_TOP_K,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        use_mmr: bool = False,
        mmr_lambda: float = DEFAULT_MMR_LAMBDA,
        metadata_filter: dict[str, object] | None = None,
        provider: str | None = None,
        temperature: float | None = DEFAULT_TEMPERATURE,
        max_tokens: int | None = DEFAULT_MAX_TOKENS,
    ) -> dict[str, object]:
        """基于知识库内容生成完整回答（检索→增强→生成），返回答案与引用片段。

        Args:
            query: 用户查询内容，支持中英文。
            top_k: 检索数量。
            similarity_threshold: 相似度阈值，低于该值的文档被过滤。
            use_mmr: 是否使用 MMR 算法增加结果多样性。
            mmr_lambda: MMR 参数，0.0=多样性优先，1.0=相关性优先。
            metadata_filter: 元数据过滤条件，如 {"file_type": "pdf"}。
            provider: LLM 提供商，为空使用默认提供商。
            temperature: 生成温度，0.0=确定性，2.0=创造性。
            max_tokens: 生成回答的最大 token 数。

        Returns:
            完整回答：answer/retrieved_docs/provider/model/tokens_used。
        """
        try:
            result = await get_rag_service().query(
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
            # 对齐 RAGQueryResponse 的字段结构，便于客户端消费；
            # retrieved_docs 需过 from_search_results 归一为领域契约
            # （RetrievedChunk：chunk_id/document_id/text/score/metadata），
            # 与 retrieve_docs 的 items 结构保持一致，否则客户端按同一契约解析会失败。
            raw_docs = result.get("retrieved_docs", []) or []
            normalized_docs = (
                [doc.model_dump() for doc in from_search_results(raw_docs)]
                if isinstance(raw_docs, list)
                else []
            )
            return {
                "answer": result.get("answer", ""),
                "retrieved_docs": normalized_docs,
                "provider": result.get("provider", ""),
                "model": result.get("model", ""),
                "tokens_used": result.get("tokens_used"),
            }
        except Exception as exc:  # noqa: BLE001 - 统一转换为 MCP 可读错误
            raise _to_mcp_error(exc) from exc


__all__ = ["register_tools"]
