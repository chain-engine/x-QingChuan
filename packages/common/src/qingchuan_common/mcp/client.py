"""MCP 客户端封装（晴川 x-QingChuan 跨服务通用件）。

基于 MCP 官方 Python SDK（mcp>=2.3.0）的 Streamable HTTP 传输实现，
面向"服务间以 MCP 协议调用工具"的标准场景：

    - streamable_http_client 是 MCP 2.x 官方推荐的 HTTP 传输（取代早期 SSE），
      与 rag-service 的 MCPServer.streamable_http_app 挂载天然匹配；
    - 每次调用走完整 MCP 握手（initialize → tools/*），自动携带会话管理，
      无需手动维护 JSON-RPC 与 mcp-session-id（对比手写客户端）。

SDK 版本注意：本仓库锁定的 mcp SDK 中 streamable_http_client 的签名为
    (url, *, http_client: httpx2.AsyncClient | None, terminate_on_close, max_sse_event_size)
即 HTTP 传输层由调用方注入 httpx2.AsyncClient（mcp SDK 的 HTTP 依赖包），
超时通过该 AsyncClient 的 timeout 参数控制，不直接传给 streamable_http_client。
（不同 mcp 版本签名不同：部分版本接收 timeout / headers 参数。）

使用（异步）:
    client = MCPClient("http://rag-service:8010/mcp")
    tools = await client.list_tools()
    result = await client.call_tool("retrieve_docs", {"query": "人社"})

使用（同步适配，供无事件循环的编排线程）:
    client.call_tool_sync("retrieve_docs", {"query": "人社"})

异常：连接/握手失败抛 MCPConnectionError；工具执行失败抛 MCPToolError；
解析失败抛 MCPResponseError。所有错误消息面向调用方可读，不泄漏内部堆栈。
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


class MCPClientError(RuntimeError):
    """MCP 客户端基础错误。"""


class MCPConnectionError(MCPClientError):
    """连接 / 握手失败（服务不可达、超时、协议拒绝）。"""


class MCPToolError(MCPClientError):
    """工具调用返回 isError=true（服务端业务错误）。"""

    def __init__(self, message: str, tool_name: str) -> None:
        super().__init__(message)
        self.tool_name = tool_name


class MCPResponseError(MCPClientError):
    """工具返回内容无法解析（非 JSON、结构异常）。"""


def _parse_tool_content(result: Any) -> dict[str, Any]:
    """把 MCP CallToolResult 归一化为结构化 dict。

    MCP 工具返回 content 为文本块。SDK 服务端对 list[dict] 返回值
    会把每个元素序列化为独立的 TextContent 块，因此这里按块逐次尝试
    JSON 解析（全部可解析时组装为列表），再回退到整段拼接解析，
    最后兜底保留纯文本。附带 is_error 标记供调用方统一消费。
    """
    text_parts: list[str] = []
    structured: dict[str, Any] | None = None
    for block in getattr(result, "content", []) or []:
        block_type = getattr(block, "type", "")
        if block_type == "text":
            text_parts.append(getattr(block, "text", "") or "")
        elif block_type in ("json", "structured_content") or hasattr(block, "json"):
            structured = getattr(block, "json", None) or structured

    if structured is not None:
        return {"is_error": bool(getattr(result, "isError", False)), **structured}

    # 方案一：逐块 JSON 解析（多块全部可解析 → 组装为列表；单块 → 直接用）
    parsed_blocks: list[Any] = []
    all_blocks_json = True
    for part in text_parts:
        if not part.strip():
            continue
        try:
            parsed_blocks.append(json.loads(part))
        except (json.JSONDecodeError, TypeError):
            all_blocks_json = False
            break
    if all_blocks_json and parsed_blocks:
        data: Any = parsed_blocks[0] if len(parsed_blocks) == 1 else parsed_blocks
        return {"is_error": bool(getattr(result, "isError", False)), "data": data}

    # 方案二：整段拼接后整体解析
    text = "\n".join(part for part in text_parts if part)
    parsed: Any = text
    if text:
        try:
            parsed = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            parsed = text
    return {
        "is_error": bool(getattr(result, "isError", False)),
        "data": parsed,
    }


def _open_stream(url: str, timeout: float):
    """构造 streamable HTTP 传输流（超时注入底层 httpx2.AsyncClient）。

    返回 (http_client, read, write) 上下文管理元组，供 ClientSession 使用。
    """
    http_client = httpx2.AsyncClient(timeout=httpx2.Timeout(timeout))
    streams = streamable_http_client(url, http_client=http_client)
    return http_client, streams


class MCPClient:
    """通用 MCP Streamable HTTP 客户端。

    Args:
        url: MCP 服务端端点（如 http://rag-service:8010/mcp）
        timeout: 单次 HTTP 请求超时秒数
    """

    def __init__(self, url: str, timeout: float = 60.0) -> None:
        if not url:
            raise ValueError("MCP url 不能为空")
        self._url = url.rstrip("/")
        self._timeout = timeout

    @property
    def url(self) -> str:
        return self._url

    # ------------------------------------------------------------------
    # 异步协议层（MCP SDK 原生形态）
    # ------------------------------------------------------------------

    async def list_tools(self) -> list[dict[str, Any]]:
        """列出服务端可用工具（含 name / description / inputSchema）。"""
        http_client, streams = _open_stream(self._url, self._timeout)
        try:
            async with streams as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    return [tool.model_dump(mode="json") for tool in tools.tools]
        except MCPClientError:
            raise
        except Exception as exc:
            raise MCPConnectionError(f"MCP 连接失败（{self._url}）：{exc}") from exc
        finally:
            await http_client.aclose()

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        """调用工具并返回结构化结果（含 is_error 标记）。

        Raises:
            MCPConnectionError: 连接 / 握手失败
            MCPToolError: 服务端工具执行返回 isError=true
            MCPResponseError: 返回内容无法解析
        """
        http_client, streams = _open_stream(self._url, self._timeout)
        try:
            async with streams as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(name, arguments or {})
        except MCPClientError:
            raise
        except Exception as exc:
            raise MCPConnectionError(f"MCP 调用失败（tool={name} @ {self._url}）：{exc}") from exc
        finally:
            await http_client.aclose()

        parsed = _parse_tool_content(result)
        if parsed.get("is_error"):
            detail = parsed.get("data", parsed.get("text", "unknown error"))
            raise MCPToolError(
                f"MCP 工具 {name} 执行失败：{detail}",
                tool_name=name,
            )
        return parsed

    # ------------------------------------------------------------------
    # 同步适配层（供无运行中事件循环的编排线程直接调用）
    # ------------------------------------------------------------------

    def list_tools_sync(self) -> list[dict[str, Any]]:
        """同步版 list_tools（内部 asyncio.run，调用方不得处于事件循环中）。"""
        return asyncio.run(self.list_tools())

    def call_tool_sync(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        """同步版 call_tool（内部 asyncio.run，调用方不得处于事件循环中）。"""
        return asyncio.run(self.call_tool(name, arguments))


__all__ = [
    "MCPClient",
    "MCPClientError",
    "MCPConnectionError",
    "MCPResponseError",
    "MCPToolError",
]
