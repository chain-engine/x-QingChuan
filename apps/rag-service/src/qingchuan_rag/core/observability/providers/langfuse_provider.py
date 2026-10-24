"""Langfuse Provider — 将观测事件翻译为 Langfuse Trace（默认可视化平台）。

实现要点（Langfuse Python SDK 5.x / OTel 架构，已按实际 API 核验）：
- 每个请求（request_id）映射为一个 Trace；trace id 直接复用 request_id（幂等、可重放、天然去重）；
- 检索三阶段（understand/candidate/rank_filter/total）合并为一个 `retriever` span；
  生成阶段一个 `generation` span（携带真实 token 用量 usage_details）；
- `trace_sample_rate` 采样（request_id 稳定哈希，同请求各事件采样结论一致）；
- `mask_query=True` 时 query 输入脱敏为占位符；
- 全部调用包 try/except，绝不向业务抛异常（Manager 另有兜底）。
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from qingchuan_rag.core.observability.base import ObservabilityProvider
from qingchuan_rag.core.observability.events import (
    FailureEvent,
    GenerationEvent,
    ObservabilityEvent,
    RagQueryEvent,
    RetrievalPhaseEvent,
)

# 未完成请求缓冲上限：超过则丢弃最老组，防止异常场景内存失控
_MAX_PENDING = 500


class LangfuseProvider(ObservabilityProvider):
    """Langfuse 平台 Provider（自托管默认可视化）。"""

    name: str = "langfuse"

    def __init__(self, settings: Any) -> None:
        obs = settings.observability
        self._host: str = obs.langfuse_host
        self._public_key: str = obs.langfuse_public_key
        self._secret_key: str = obs.langfuse_secret_key
        self._sample_rate: float = obs.trace_sample_rate
        self._mask_query: bool = obs.mask_query
        self._client: Any = None
        self._pending: dict[str, list[ObservabilityEvent]] = {}

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    def initialize(self) -> None:
        from langfuse import Langfuse  # 懒加载：SDK 缺失时不影响业务启动

        if not self._public_key or not self._secret_key:
            raise ValueError("LangfuseProvider: public_key/secret_key 未配置")
        self._client = Langfuse(
            # SDK 5.x：host 已废弃，OTLP exporter 与 Public API 均走 base_url
            base_url=self._host,
            public_key=self._public_key,
            secret_key=self._secret_key,
        )

    def shutdown(self) -> None:
        client = self._client
        self._client = None
        self._pending.clear()
        if client is None:
            return
        try:
            client.flush()
            client.shutdown()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 事件处理
    # ------------------------------------------------------------------
    def handle_event(self, event: ObservabilityEvent) -> None:
        client = self._client
        if client is None:
            return
        try:
            if isinstance(event, (RetrievalPhaseEvent, GenerationEvent)):
                # 阶段事件先缓冲，待 RagQueryEvent（请求级收尾）统一归组
                self._pending.setdefault(event.request_id or "-", []).append(event)
                if len(self._pending) > _MAX_PENDING:
                    oldest = next(iter(self._pending))
                    self._pending.pop(oldest, None)
            elif isinstance(event, RagQueryEvent):
                self._flush_query(client, event)
            elif isinstance(event, FailureEvent):
                self._flush_failure(client, event)
        except Exception:
            # Provider 内部异常绝不外泄（Manager 亦有兜底）
            pass

    # ------------------------------------------------------------------
    # 采样与脱敏
    # ------------------------------------------------------------------
    def _sampled(self, request_id: str) -> bool:
        rate = self._sample_rate
        if rate >= 1.0:
            return True
        if rate <= 0.0:
            return False
        digest = hashlib.md5(request_id.encode("utf-8")).hexdigest()[:8]
        bucket = int(digest, 16) % 10_000
        return bucket < int(rate * 10_000)

    def _mask(self, query: str) -> str:
        return "[masked]" if self._mask_query else query

    @staticmethod
    def _epoch_ms(dt: datetime | None) -> int | None:
        """datetime → epoch 毫秒（Langfuse end_time 需要 int 毫秒）。"""
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return int(dt.timestamp() * 1000)

    @staticmethod
    def _trace_id(request_id: str) -> str:
        """Langfuse trace id 必须是 32 位小写 hex；否则用 md5 稳定映射（幂等可重放）。"""
        if len(request_id) == 32 and all(c in "0123456789abcdef" for c in request_id):
            return request_id
        return hashlib.md5(request_id.encode("utf-8")).hexdigest()

    @staticmethod
    def _usage(langfuse: Any, tokens: dict | None) -> dict[str, int] | None:
        """业务 tokens dict → Langfuse usage_details 规范键。"""
        if not tokens:
            return None
        usage: dict[str, int] = {}
        if tokens.get("prompt_tokens") is not None:
            usage["input"] = int(tokens["prompt_tokens"])
        if tokens.get("completion_tokens") is not None:
            usage["output"] = int(tokens["completion_tokens"])
        if tokens.get("total_tokens") is not None:
            usage["total"] = int(tokens["total_tokens"])
        return usage or None

    # ------------------------------------------------------------------
    # 组装
    # ------------------------------------------------------------------
    def _flush_query(self, client: Any, event: RagQueryEvent) -> None:
        rid = event.request_id or "-"
        pending = self._pending.pop(rid, [])
        if not self._sampled(rid):
            return

        from langfuse.types import TraceContext

        retrieval_events = [e for e in pending if isinstance(e, RetrievalPhaseEvent)]
        gen_events = [e for e in pending if isinstance(e, GenerationEvent)]

        trace_id = self._trace_id(rid)
        root = client.start_observation(
            trace_context=TraceContext(trace_id=trace_id),
            name="rag_query",
            as_type="chain",
            input=self._mask(event.query),
            metadata={
                "query_len": event.query_len,
                "top_k": event.top_k,
                "status": event.status,
                "error_type": event.error_type,
                "latencies_ms": event.latencies,
            },
        )

        # 检索 span：合并三阶段 + total
        if retrieval_events:
            stages: dict[str, dict[str, Any]] = {}
            for e in retrieval_events:
                detail: dict[str, Any] = {"latency_ms": round(e.latency_ms, 2)}
                if e.candidates is not None:
                    detail["candidates"] = e.candidates
                if e.retrieved is not None:
                    detail["retrieved"] = e.retrieved
                if e.empty_reason is not None:
                    detail["empty_reason"] = e.empty_reason
                stages[e.stage] = detail
            end_ms = self._epoch_ms(
                max((e.ended_at for e in retrieval_events if e.ended_at), default=None)
            )
            root.start_observation(
                name="retrieval",
                as_type="retriever",
                metadata={"stages": stages},
            ).end(end_time=end_ms)

        # 生成 span：真实 token 用量
        gen = gen_events[-1] if gen_events else None
        usage = self._usage(client, gen.tokens if gen else event.tokens)
        model = (gen.model if gen else None) or event.model or "unknown"
        if gen is not None:
            root.start_observation(
                name="generation",
                as_type="generation",
                model=model,
                usage_details=usage,
                metadata={"latency_ms": round(gen.latency_ms, 2)},
            ).end(end_time=self._epoch_ms(gen.ended_at))
        elif event.tokens or event.status == "ok":
            # 无 GenerationEvent（如 CLI 直调），用总览数据兜底
            root.start_observation(
                name="generation",
                as_type="generation",
                model=model,
                usage_details=usage,
            ).end(end_time=self._epoch_ms(event.ended_at))

        if event.status == "error":
            root.update(level="ERROR", status_message=event.error_type or "error")
        root.end(end_time=self._epoch_ms(event.ended_at))

    def _flush_failure(self, client: Any, event: FailureEvent) -> None:
        rid = event.request_id or "-"
        if not self._sampled(rid):
            return
        try:
            from langfuse.types import TraceContext

            client.create_event(
                trace_context=TraceContext(trace_id=self._trace_id(rid)),
                name=f"failure:{event.phase}",
                metadata={
                    "error_type": event.error_type,
                    "message": event.message,
                },
                level="ERROR",
            )
        except Exception:
            pass


__all__ = ["LangfuseProvider"]
