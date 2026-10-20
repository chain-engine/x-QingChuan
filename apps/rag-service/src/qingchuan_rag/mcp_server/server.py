#!/usr/bin/env python3
"""MCP 服务装配层：MCPServer 实例 + 三大原语的统一注册入口。

目录按 MCP 协议原语组织，新增能力时只改对应模块的注册函数：
    - tools.py      → Tools（工具）：当前暴露 retrieve_docs / rag_query（只读）
    - prompts.py    → Prompts（提示词模板）：预留，按需开放
    - resources.py  → Resources（资源）：预留，按需开放

依赖方向：本层（mcp_server/）只依赖共享业务核心（services/ 等），
与 HTTP 接入层（http_server/）互不依赖、平级对称。
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from qingchuan_rag.mcp_server import prompts, resources, tools
from qingchuan_rag.services.rag_service import RAGService

# ---------------------------------------------------------------------------
# MCP 服务实例
# ---------------------------------------------------------------------------

mcp_server = MCPServer(
    name="x-qingchuan",
    title="晴川（QingChuan）",
    description="支持 HTTP 与 MCP 双挂载的 RAG 检索增强生成服务：以人社系统离线数据"
    "为知识源，按查询检索相关片段或生成完整回答。",
    instructions=(
        "晴川（QingChuan）是一个 RAG 一体化服务，通过 MCP 协议提供以下工具：\n"
        "1. retrieve_docs：按查询检索知识库中最相关的文档片段（仅检索，不生成），"
        "返回 Top-K 片段及其元数据，适合将检索结果注入自身 prompt 的编排场景；\n"
        "2. rag_query：基于知识库内容生成完整回答（检索→增强→生成流水线），"
        "适合直接获取自然语言答案的场景。\n\n"
        "知识库数据由人社系统离线索引周期同步，所有操作均记录审计日志。"
    ),
)

# RAG 服务引用：由 main.lifespan 调用 bind_rag_service() 注入，复用同一实例
_rag_service: RAGService | None = None


def bind_rag_service(service: RAGService) -> None:
    """绑定 RAG 服务实例（应用启动时注入，避免重复初始化基础设施）"""
    global _rag_service
    _rag_service = service


def get_rag_service() -> RAGService:
    """获取已绑定的 RAG 服务，未初始化时抛出可读错误"""
    if _rag_service is None:
        raise RuntimeError("RAG service not bound. Call bind_rag_service() first.")
    return _rag_service


# ---------------------------------------------------------------------------
# 原语注册（扩展入口）
# ---------------------------------------------------------------------------


def _register_all() -> None:
    """注册全部 MCP 原语。

    新增能力约定：
    - 新工具 → tools.register_tools 内加 @server.tool() 函数；
    - 新提示语 → prompts.register_prompts 内启用 @server.prompt()；
    - 新资源 → resources.register_resources 内启用 @server.resource()。
    保持"只读 + 复用 services"原则：写操作继续走 HTTP 管理面。
    """
    tools.register_tools(mcp_server, get_rag_service)
    prompts.register_prompts(mcp_server)
    resources.register_resources(mcp_server)


_register_all()


__all__ = ["mcp_server", "bind_rag_service", "get_rag_service"]
