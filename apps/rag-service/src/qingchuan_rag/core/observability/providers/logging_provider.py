"""LoggingProvider：事件 → loguru JSON 摘要日志（兜底通道，永远可用）。

日志管道（request_id、JSON 序列化）复用 core/logger.py 既有设施；
每事件一条结构化日志，Loki/ELK 可直接聚合，按 request_id 追全链路。
"""

from __future__ import annotations

from qingchuan_rag.core.logger import logger
from qingchuan_rag.core.observability.base import ObservabilityProvider
from qingchuan_rag.core.observability.events import (
    FailureEvent,
    GenerationEvent,
    HttpRequestEvent,
    ObservabilityEvent,
    RagQueryEvent,
    RetrievalPhaseEvent,
)


class LoggingProvider(ObservabilityProvider):
    """事件 → 结构化 JSON 日志。"""

    name = "logging"

    def handle_event(self, event: ObservabilityEvent) -> None:
        if isinstance(event, RetrievalPhaseEvent):
            logger.bind(
                event="retrieval_phase",
                stage=event.stage,
                latency_ms=round(event.latency_ms, 2),
                candidates=event.candidates,
                retrieved=event.retrieved,
                empty_reason=event.empty_reason,
            ).debug(f"Retrieval phase [{event.stage}] completed")
        elif isinstance(event, GenerationEvent):
            logger.bind(
                event="generation",
                model=event.model,
                latency_ms=round(event.latency_ms, 2),
                tokens=event.tokens,
            ).info("LLM generation completed")
        elif isinstance(event, RagQueryEvent):
            log = logger.bind(
                event="rag_query",
                query_len=event.query_len,
                top_k=event.top_k,
                latency_ms=event.latencies,
                tokens=event.tokens,
                provider=event.provider,
                model=event.model,
                status=event.status,
                error_type=event.error_type,
            )
            if event.status == "error":
                log.error(f"RAG query failed: {event.error_type}")
            elif event.status == "empty":
                log.warning("RAG query returned empty retrieval")
            else:
                log.info("RAG query completed")
        elif isinstance(event, HttpRequestEvent):
            logger.bind(
                event="http_request",
                endpoint=event.endpoint,
                status_class=event.status_class,
                latency_ms=round(event.latency_ms, 2),
            ).info("HTTP request completed")
        elif isinstance(event, FailureEvent):
            logger.bind(
                event="failure",
                phase=event.phase,
                error_type=event.error_type,
            ).warning(f"Observability failure [{event.phase}]: {event.error_type}")


__all__ = ["LoggingProvider"]
