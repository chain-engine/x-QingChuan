"""rag-service HTTP 黑盒客户端（解析统一响应包裹 {code, message, data, request_id}）。"""

from __future__ import annotations

from typing import Any

import httpx

from qingchuan_eval.schema import EvalConfig


class EvalClientError(RuntimeError):
    """评测客户端错误（请求失败 / 响应异常 / 业务错误）。"""


class RagClient:
    """对 rag-service /api/v1 的轻量黑盒客户端。"""

    def __init__(self, config: EvalConfig):
        self._config = config
        self._client = httpx.Client(timeout=config.timeout)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> RagClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        similarity_threshold: float | None = None,
        use_mmr: bool | None = None,
        mmr_lambda: float | None = None,
    ) -> list[dict[str, Any]]:
        """调用 /rag/retrieve，返回 RetrievedChunk dict 列表（按相关性降序）。

        响应契约以共享领域包 qingchuan_domain 为准：data 含 chunks / total
        （chunks 键，领域 RetrievalResponse；早期 documents 键已统一收敛）。
        """
        cfg = self._config
        thr = similarity_threshold if similarity_threshold is not None else cfg.similarity_threshold
        payload: dict[str, Any] = {
            "query": query,
            "top_k": top_k if top_k is not None else cfg.top_k,
            "similarity_threshold": thr,
            "use_mmr": use_mmr if use_mmr is not None else cfg.use_mmr,
            "mmr_lambda": mmr_lambda if mmr_lambda is not None else cfg.mmr_lambda,
        }
        data = self._post(cfg.retrieve_url, payload)
        chunks = data.get("chunks") or []
        if not isinstance(chunks, list):
            raise EvalClientError("retrieve 响应 chunks 非列表")
        return chunks

    def query(
        self,
        query: str,
        top_k: int | None = None,
        similarity_threshold: float | None = None,
    ) -> dict[str, Any]:
        """调用 /rag/query（full 模式），返回 RAG 问答结果 dict。"""
        cfg = self._config
        thr = similarity_threshold if similarity_threshold is not None else cfg.similarity_threshold
        payload: dict[str, Any] = {
            "query": query,
            "top_k": top_k if top_k is not None else cfg.top_k,
            "similarity_threshold": thr,
        }
        return self._post(cfg.query_url, payload)

    def _post(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            resp = self._client.post(url, json=payload)
        except httpx.HTTPError as e:
            raise EvalClientError(f"请求失败 {url}: {e}") from e
        if resp.status_code >= 400:
            raise EvalClientError(f"HTTP {resp.status_code} {url}: {resp.text[:300]}")
        try:
            body = resp.json()
        except ValueError as e:
            raise EvalClientError(f"响应非 JSON {url}: {resp.text[:200]}") from e
        if body.get("code") not in (0, None):
            raise EvalClientError(f"业务错误 code={body.get('code')}: {body.get('message')}")
        data = body.get("data")
        if data is None:
            raise EvalClientError(f"响应缺少 data 字段: {url}")
        return data
