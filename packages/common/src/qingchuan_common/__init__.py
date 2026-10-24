"""晴川（x-QingChuan）跨服务通用件。

通用能力（供多服务复用）：
    - qingchuan_common.mcp：MCP 官方 SDK 的 Streamable HTTP 客户端封装，
      agent-service 经此以 MCP 协议调用 rag-service 工具（检索 / 问答）。
    - qingchuan_common.http：统一 HTTP 响应信封（ApiResponse / success_response 等）。
"""

from qingchuan_common import http, mcp

__version__ = "0.1.0"

__all__ = ["http", "mcp"]
