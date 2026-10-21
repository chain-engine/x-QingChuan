#!/usr/bin/env python3
"""晴川（QingChuan）MCP 客户端：通过 MCP 协议调用晴川 rag-service 的检索能力。

晴川为内部服务，不设机器身份鉴权，本客户端不再计算签名，
直接走 MCP streamable HTTP 握手（initialize → notifications/initialized → tools/*）。

两种使用方式：

1. 命令行方式（快速验证）：
    python scripts/qingchuan_mcp_client.py --list                       # 列出工具
    python scripts/qingchuan_mcp_client.py --tool rag_query --query "什么是RAG技术？"
    python scripts/qingchuan_mcp_client.py --tool retrieve_docs --query "人社" --top-k 3

2. 编程方式（集成进自己的 Agent 代码）：
    from scripts.qingchuan_mcp_client import QingChuanMcpClient
    client = QingChuanMcpClient("http://127.0.0.1:8010/mcp")
    client.initialize()
    tools = client.list_tools()
    result = client.call_tool("rag_query", {"query": "什么是RAG技术？", "top_k": 3})

说明：
    - 走完整 MCP streamable HTTP 握手，自动携带 mcp-session-id，
      并兼容 JSON 与 SSE 两种响应格式；
    - verbose=True 时打印每个 JSON-RPC 请求的请求头、请求体与原始响应。
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from typing import Any

import requests

MCP_PATH = "/mcp"  # 与 main.py 中 mount 路径一致


class QingChuanMcpClient:
    """晴川 MCP 客户端：JSON-RPC over Streamable HTTP，会话管理。"""

    def __init__(
        self,
        base_url: str,
        verbose: bool = True,
        timeout: int = 90,
    ) -> None:
        # base_url 形如 http://127.0.0.1:8010 或 http://127.0.0.1:8010/mcp，统一收敛到 /mcp
        self.endpoint = base_url.rstrip("/") + (
            "" if base_url.rstrip("/").endswith(MCP_PATH) else MCP_PATH
        )
        self.verbose = verbose
        self.timeout = timeout
        self.session_id: str | None = None

    # ── 传输层：POST JSON-RPC + 解析响应 ─────────────────────────────
    def _post(self, payload: dict) -> dict:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers: dict[str, str] = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        if self.session_id:
            headers["mcp-session-id"] = self.session_id

        if self.verbose:
            print(f"\n── POST {self.endpoint} ────────────────────────────────")
            print("请求头:", json.dumps(headers, ensure_ascii=False))
            print("请求体:", body.decode("utf-8"))

        resp = requests.post(self.endpoint, headers=headers, data=body, timeout=self.timeout)

        if self.verbose:
            print("响应状态:", resp.status_code)
            print("响应头:", json.dumps(dict(resp.headers.items()), ensure_ascii=False))

        # MCP 服务端在 initialize 时通过响应头下发 session id
        sid = resp.headers.get("mcp-session-id")
        if sid:
            self.session_id = sid

        # 强制 UTF-8 解码（SSE 无 charset 时 requests 会误用 latin-1，导致中文乱码/解析失败）
        text = resp.content.decode("utf-8", errors="replace")
        if self.verbose:
            print("响应体:", text[:1200] or "(空)")
        if resp.status_code >= 400:
            raise RuntimeError(f"MCP 请求失败 HTTP {resp.status_code}: {text[:300]}")
        # 202/204：通知类请求（如 notifications/initialized）正常无响应体
        if resp.status_code in (202, 204) or not text.strip():
            return {}
        return self._parse_response(text)

    @staticmethod
    def _parse_response(text: str) -> dict:
        """兼容 JSON 直出与 SSE 两种响应格式。"""
        stripped = text.strip()
        if not stripped.startswith("{"):
            lines = [
                line[5:].strip()
                for line in stripped.splitlines()
                if line.startswith("data:") and not line.startswith("data: [DONE]")
            ]
            data = "\n".join(lines)
            parsed = json.loads(data)
            if isinstance(parsed, dict) and parsed.get("type") == "message":
                parsed = parsed.get("message", parsed)
            return parsed
        return json.loads(stripped)

    # ── MCP 协议层 ─────────────────────────────────────────────────────
    def initialize(self) -> dict:
        """MCP 握手：initialize（拿 session id）+ notifications/initialized。"""
        request_id = str(uuid.uuid4())
        result = self._post(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {"tools": {}},
                    "clientInfo": {"name": "qingchuan-mcp-client", "version": "0.1.0"},
                },
            }
        )
        if self.verbose:
            version = result.get("result", {}).get("protocolVersion")
            print(f"\n✓ initialize 成功，protocolVersion={version}")
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return result

    def list_tools(self) -> list[dict]:
        """列出服务端可用工具。"""
        result = self._post(
            {"jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": "tools/list", "params": {}}
        )
        tools = result.get("result", {}).get("tools", [])
        if self.verbose:
            print(f"\n✓ 工具列表（共 {len(tools)} 个）：")
            for tool in tools:
                print(f"  - {tool['name']}: {tool.get('description', '')[:60]}")
        return tools

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict:
        """调用指定工具并打印返回内容。"""
        if self.verbose:
            print(f"\n→ 调用工具 {name}({json.dumps(arguments, ensure_ascii=False)})")
        result = self._post(
            {
                "jsonrpc": "2.0",
                "id": str(uuid.uuid4()),
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        )
        if self.verbose:
            for item in result.get("result", {}).get("content", []):
                if item.get("type") == "text":
                    print(f"\n✓ 工具返回：\n{item.get('text', '')[:1000]}")
                elif item.get("type") == "json":
                    print(
                        f"\n✓ 工具返回(JSON)：\n{json.dumps(item.get('json', {}), ensure_ascii=False, indent=2)[:1500]}"
                    )
            if result.get("result", {}).get("isError"):
                print("\n⚠ 工具执行返回错误标志 isError=true")
        return result


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="晴川 MCP 客户端（模拟外部 Agent 接入）",
        epilog="示例：\n"
        "  python scripts/qingchuan_mcp_client.py --list\n"
        '  python scripts/qingchuan_mcp_client.py --tool rag_query --query "什么是RAG技术？"\n'
        '  python scripts/qingchuan_mcp_client.py --tool retrieve_docs --query "人社" --top-k 3',
    )
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8010/mcp",
        help="MCP 端点（默认 http://127.0.0.1:8010/mcp）",
    )
    parser.add_argument("--list", action="store_true", help="仅列出工具列表")
    parser.add_argument("--tool", choices=["rag_query", "retrieve_docs"], help="要调用的工具名")
    parser.add_argument("--query", default="什么是RAG技术？", help="查询内容")
    parser.add_argument("--top-k", type=int, default=3, help="返回片段数")
    parser.add_argument("--quiet", action="store_true", help="关闭详细日志")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    client = QingChuanMcpClient(args.url, verbose=not args.quiet)
    try:
        client.initialize()
        tools = client.list_tools()
        if args.list:
            return 0
        if not args.tool:
            print("\n未指定 --tool，仅完成握手与工具列表。示例：--tool rag_query --query 'xxx'")
            return 0
        if args.tool not in {t["name"] for t in tools}:
            print(f"工具 {args.tool} 不在服务端列表中")
            return 1
        client.call_tool(args.tool, {"query": args.query, "top_k": args.top_k})
        return 0
    except Exception as exc:  # noqa: BLE001 - 客户端统一兜底
        print(f"\n✗ MCP 调用失败：{exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
