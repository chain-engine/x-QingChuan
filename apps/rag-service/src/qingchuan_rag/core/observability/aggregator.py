"""本地窗口聚合器（AggregatorProvider）：率/分布指标 → GET /obs/stats。

Langfuse 擅长 trace 级排障；"系统整体健康"（空召回率、失败率、P50/P95/P99、
tokens 分布、召回数分布）由本聚合器在内存滚动窗口中实时计算，零外部依赖。

- 滚动窗口：1h / 24h，懒清理过期样本；
- 分位数：样本排序后线性插值（P50/P95/P99）；
- 所有计数按事件驱动，与 Langfuse 同一批事件，口径一致。
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from statistics import mean
from typing import Any

from qingchuan_rag.core.observability.base import ObservabilityProvider
from qingchuan_rag.core.observability.events import (
    FailureEvent,
    GenerationEvent,
    HttpRequestEvent,
    ObservabilityEvent,
    RagQueryEvent,
    RetrievalPhaseEvent,
)

# 召回数直方图桶（[下界, 上界)）
_RETRIEVED_BUCKETS: list[tuple[float, float]] = [
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 5),
    (5, 8),
    (8, 10),
    (10, 20),
    (20, float("inf")),
]


class RollingWindow:
    """滚动时间窗口：按 key 存 (timestamp, value)，懒清理。"""

    def __init__(self, window_seconds: float, max_items: int = 200_000) -> None:
        self._window = window_seconds
        self._max_items = max_items
        self._series: dict[str, deque[tuple[float, float]]] = defaultdict(deque)
        self._flags: dict[str, deque[tuple[float, str]]] = defaultdict(deque)

    def _clean_series(self, key: str, now: float) -> None:
        dq = self._series[key]
        cutoff = now - self._window
        while dq and dq[0][0] < cutoff:
            dq.popleft()
        while len(dq) > self._max_items:
            dq.popleft()

    def _clean_flags(self, key: str, now: float) -> None:
        dq = self._flags[key]
        cutoff = now - self._window
        while dq and dq[0][0] < cutoff:
            dq.popleft()
        while len(dq) > self._max_items:
            dq.popleft()

    def add(self, key: str, value: float, now: float | None = None) -> None:
        now = time.time() if now is None else now
        self._series[key].append((now, float(value)))
        self._clean_series(key, now)

    def flag(self, key: str, label: str, now: float | None = None) -> None:
        now = time.time() if now is None else now
        self._flags[key].append((now, label))
        self._clean_flags(key, now)

    # ---- 统计 ----
    def values(self, key: str) -> list[float]:
        self._clean_series(key, time.time())
        return [v for _, v in self._series[key]]

    def percentile(self, key: str, q: float) -> float | None:
        vals = sorted(self.values(key))
        if not vals:
            return None
        idx = (len(vals) - 1) * q
        lo = int(idx)
        hi = min(lo + 1, len(vals) - 1)
        frac = idx - lo
        return vals[lo] + (vals[hi] - vals[lo]) * frac

    def label_counts(self, key: str) -> dict[str, int]:
        self._clean_flags(key, time.time())
        out: dict[str, int] = {}
        for _, label in self._flags[key]:
            out[label] = out.get(label, 0) + 1
        return out


def _bucket_of(value: float) -> str:
    for lo, hi in _RETRIEVED_BUCKETS:
        if lo <= value < hi:
            return f"{lo:g}-{hi:g}" if hi != float("inf") else f"{lo:g}+"
    return "unknown"


class AggregatorProvider(ObservabilityProvider):
    """把事件聚合成窗口指标，供 /obs/stats 消费。"""

    name = "aggregator"

    def __init__(self, windows_seconds: tuple[float, ...] = (3600.0, 86400.0)) -> None:
        self._windows: dict[str, RollingWindow] = {
            f"{int(s)}s": RollingWindow(s) for s in windows_seconds
        }
        self._series_keys = {
            "retrieval_latency_ms",
            "generation_latency_ms",
            "generation_prompt_tokens",
            "generation_completion_tokens",
            "generation_total_tokens",
            "retrieved_docs",
            "candidates",
            "request_latency_ms",
        }

    # ---- 事件 → 窗口 ----
    def handle_event(self, event: ObservabilityEvent) -> None:
        if isinstance(event, RetrievalPhaseEvent):
            for win in self._windows.values():
                win.add("retrieval_latency_ms", event.latency_ms)
                if event.stage == "total":
                    win.add("retrieved_docs", event.retrieved)
                    win.add("candidates", event.candidates)
                    if event.empty_reason:
                        win.flag("empty_retrieval", event.empty_reason)
        elif isinstance(event, GenerationEvent):
            for win in self._windows.values():
                win.add("generation_latency_ms", event.latency_ms)
                if event.tokens:
                    win.add("generation_prompt_tokens", event.tokens.get("prompt_tokens") or 0)
                    win.add(
                        "generation_completion_tokens",
                        event.tokens.get("completion_tokens") or 0,
                    )
                    win.add("generation_total_tokens", event.tokens.get("total_tokens") or 0)
        elif isinstance(event, RagQueryEvent):
            for win in self._windows.values():
                win.add("request_latency_ms", event.latencies.get("total", 0.0))
                if event.tokens:
                    win.add(
                        "generation_total_tokens", event.tokens.get("total_tokens") or 0
                    )
        elif isinstance(event, HttpRequestEvent):
            for win in self._windows.values():
                win.flag("http_status", event.status_class)
                win.add("request_latency_ms", event.latency_ms)
        elif isinstance(event, FailureEvent):
            for win in self._windows.values():
                win.flag("failures", event.phase)

    # ---- 快照 ----
    def _window_snapshot(self, win: RollingWindow) -> dict[str, Any]:
        empty = win.label_counts("empty_retrieval")
        statuses = win.label_counts("http_status")
        failures = win.label_counts("failures")
        http_total = sum(statuses.values())
        fail_total = sum(failures.values())
        retrieval_total = len(win.values("retrieval_latency_ms"))

        retrieved_vals = win.values("retrieved_docs")
        retrieved_hist: dict[str, int] = {}
        for v in retrieved_vals:
            k = _bucket_of(v)
            retrieved_hist[k] = retrieved_hist.get(k, 0) + 1

        return {
            "requests": http_total,
            "retrieval_requests": retrieval_total,
            "retrieval_latency_ms": {
                "p50": win.percentile("retrieval_latency_ms", 0.5),
                "p95": win.percentile("retrieval_latency_ms", 0.95),
                "p99": win.percentile("retrieval_latency_ms", 0.99),
                "count": retrieval_total,
            },
            "retrieved_docs": {
                "mean": round(mean(retrieved_vals), 2) if retrieved_vals else None,
                "histogram": retrieved_hist,
                "count": len(retrieved_vals),
            },
            "empty_retrieval": {
                "total": sum(empty.values()),
                "rate": round(sum(empty.values()) / retrieval_total, 4)
                if retrieval_total
                else None,
                "reasons": empty,
            },
            "generation_tokens": {
                "prompt_p95": win.percentile("generation_prompt_tokens", 0.95),
                "completion_p95": win.percentile("generation_completion_tokens", 0.95),
                "total_p95": win.percentile("generation_total_tokens", 0.95),
                "prompt_mean": round(mean(win.values("generation_prompt_tokens")), 1)
                if win.values("generation_prompt_tokens")
                else None,
                "completion_mean": round(mean(win.values("generation_completion_tokens")), 1)
                if win.values("generation_completion_tokens")
                else None,
            },
            "failures": {
                "total": fail_total,
                "by_phase": failures,
                "rate": round(fail_total / http_total, 4) if http_total else None,
            },
            "http_5xx_rate": round(statuses.get("5xx", 0) / http_total, 4)
            if http_total
            else None,
        }

    def snapshot(self) -> dict[str, Any]:
        return {
            f"window_{key}": self._window_snapshot(win)
            for key, win in self._windows.items()
        }


__all__ = ["AggregatorProvider", "RollingWindow"]
