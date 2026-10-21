"""MCP 客户端封装包（晴川跨服务通用件）。

提供基于 MCP 官方 Python SDK 的 Streamable HTTP 客户端，
供 agent-service 等多服务以 MCP 协议调用 rag-service 等能力。
"""

from qingchuan_common.mcp.client import (
    MCPClient,
    MCPClientError,
    MCPConnectionError,
    MCPResponseError,
    MCPToolError,
)

__all__ = [
    "MCPClient",
    "MCPClientError",
    "MCPConnectionError",
    "MCPResponseError",
    "MCPToolError",
]
