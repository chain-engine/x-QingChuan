#!/usr/bin/env python3
"""晴川（QingChuan）HTTP 客户端：调用晴川 rag-service 的 HTTP 开放接口。

晴川为内部服务，不设机器身份鉴权（审计统一记 internal），
本客户端不再计算签名，仅携带 JSON Content-Type 直接请求。

两种使用方式：

1. 命令行方式（快速验证/调试）：
    python scripts/qingchuan_http_client.py --url http://127.0.0.1:8010/api/v1/rag/stats --method GET
    python scripts/qingchuan_http_client.py --url http://127.0.0.1:8010/api/v1/rag/query \
        --method POST --body-file body.json

2. 编程方式（集成进自己的代码）：
    from scripts.qingchuan_http_client import QingChuanHTTPClient
    client = QingChuanHTTPClient("http://127.0.0.1:8010")
    data = client.rag_query("什么是RAG技术？", top_k=3)      # -> 响应 JSON 的 data 字段
    stats = client.rag_stats()                                # -> 响应 JSON 的 data 字段

注意：
    - Windows PowerShell 传参时双引号会被剥离，含引号的 JSON 请用 --body-file；
    - 同步触发接口 POST /api/v1/sync/trigger 也可用本客户端调用。
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import requests


class QingChuanHTTPClient:
    """晴川 HTTP 客户端（无签名，直接调用）。"""

    def __init__(
        self,
        base_url: str,
        verbose: bool = True,
        timeout: int = 90,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.verbose = verbose
        self.timeout = timeout

    # ── 核心请求方法 ──────────────────────────────────────────────
    def request(self, method: str, path: str, body: Any = None) -> dict[str, Any]:
        """发起一个接口请求并返回响应 JSON（dict）。

        Args:
            method: HTTP 方法（GET/POST/PUT/DELETE）。
            path: 接口路径（含前缀），如 /api/v1/rag/query、/api/v1/sync/trigger。
            body: 请求体。可为 dict/list（自动 JSON 序列化）、str（按原文发送）或 None。

        Returns:
            服务端响应 JSON（含 code/message/data/request_id）。

        Raises:
            RuntimeError: 请求异常或响应非 2xx。
        """
        url = f"{self.base_url}{path}"

        payload: bytes
        body_display: str | None
        if body is None:
            payload, body_display = b"", None
        elif isinstance(body, (dict, list)):
            body_display = json.dumps(body, ensure_ascii=False)
            payload = body_display.encode("utf-8")
        elif isinstance(body, str):
            body_display = body
            payload = body.encode("utf-8")
        else:
            raise TypeError(f"不支持的 body 类型: {type(body)}")

        headers = {"Content-Type": "application/json"}

        if self.verbose:
            print(f"请求        : {method} {url}")
            if body_display is not None:
                print(f"请求体      : {body_display}")

        try:
            resp = requests.request(
                method, url, headers=headers, data=payload or None, timeout=self.timeout
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"请求异常：{exc}") from exc

        print(f"响应状态    : {resp.status_code}")
        print("响应体      :")
        try:
            result = resp.json()
        except ValueError:
            result = {"raw": resp.text[:2000]}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if resp.status_code >= 400:
            raise RuntimeError(
                f"接口返回 HTTP {resp.status_code}：{json.dumps(result, ensure_ascii=False)[:300]}"
            )
        return result

    # ── 便捷方法（按接口语义封装） ─────────────────────────────────
    def rag_query(self, query: str, top_k: int = 3, **kwargs: Any) -> dict[str, Any]:
        """RAG 问答（检索 → 增强 → 生成）。"""
        body = {"query": query, "top_k": top_k, **kwargs}
        return self.request("POST", "/api/v1/rag/query", body=body)["data"]

    def rag_retrieve(self, query: str, top_k: int = 3, **kwargs: Any) -> dict[str, Any]:
        """仅检索（不经过 LLM 生成）。"""
        body = {"query": query, "top_k": top_k, **kwargs}
        return self.request("POST", "/api/v1/rag/retrieve", body=body)["data"]

    def rag_stats(self) -> dict[str, Any]:
        """向量库统计。"""
        return self.request("GET", "/api/v1/rag/stats")["data"]

    def sync_trigger(self, full: bool = False, force: bool = False) -> dict[str, Any]:
        """触发人社数据同步（晴川差异化能力）。"""
        body = {"full": full, "force": force}
        return self.request("POST", "/api/v1/sync/trigger", body=body)["data"]

    def sync_status(self) -> dict[str, Any]:
        """最近一次同步状态。"""
        return self.request("GET", "/api/v1/sync/status")["data"]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="晴川 HTTP 客户端（直接调用，无签名）",
        epilog="示例：\n"
        "  python scripts/qingchuan_http_client.py --url http://127.0.0.1:8010/api/v1/rag/stats\n"
        "  python scripts/qingchuan_http_client.py --url http://127.0.0.1:8010/api/v1/rag/query "
        "--method POST --body-file body.json",
    )
    parser.add_argument(
        "--url", required=True, help="完整请求 URL，如 http://127.0.0.1:8010/api/v1/rag/query"
    )
    parser.add_argument(
        "--method", default="GET", help="HTTP 方法（GET/POST/PUT/DELETE），默认 GET"
    )
    parser.add_argument(
        "--body", default=None, help='请求体 JSON 字符串（POST/PUT 时传入，如 \'{"query":"xxx"}\'）'
    )
    parser.add_argument(
        "--body-file",
        default=None,
        help="从文件读取请求体 JSON（UTF-8）。Windows PowerShell 传参时双引号会被剥离，"
        "含引号的 JSON 建议用 --body-file",
    )
    parser.add_argument("--quiet", action="store_true", help="关闭请求过程日志（仅打印响应）")
    parser.add_argument(
        "--timeout", type=int, default=90, help="请求超时秒数（默认 90，embedding 冷启动可调大）"
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    try:
        body: Any
        if args.body_file:
            with open(args.body_file, encoding="utf-8") as fh:
                body = fh.read()
        elif args.body is not None:
            body = args.body
        else:
            body = None
        client = QingChuanHTTPClient(
            base_url=args.url,
            verbose=not args.quiet,
            timeout=args.timeout,
        )
        client.request(args.method, "", body=body)
        return 0
    except (RuntimeError, TypeError, OSError) as exc:
        print(f"✗ {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
