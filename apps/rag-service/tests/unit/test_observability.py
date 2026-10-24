"""可观测性模块单元测试：事件、聚合器、Manager 隔离、LangfuseProvider（mock client）。"""

from __future__ import annotations

from datetime import UTC, datetime

from qingchuan_rag.core.observability import manager, reset_request_id, set_request_id
from qingchuan_rag.core.observability.aggregator import AggregatorProvider
from qingchuan_rag.core.observability.base import ObservabilityProvider
from qingchuan_rag.core.observability.events import (
    FailureEvent,
    GenerationEvent,
    ObservabilityEvent,
    RagQueryEvent,
    RetrievalPhaseEvent,
)
from qingchuan_rag.core.observability.providers.langfuse_provider import LangfuseProvider


# ---------------------------------------------------------------------------
# 辅助：stub settings / stub client
# ---------------------------------------------------------------------------
class _StubObs:
    langfuse_host = "http://localhost:3000"
    langfuse_public_key = "pk-test"
    langfuse_secret_key = "sk-test"
    trace_sample_rate = 1.0
    mask_query = False


class _StubSettings:
    observability = _StubObs()


class _StubSpan:
    def __init__(self, client) -> None:
        self._client = client

    def end(self, **kw):
        self._client.calls.append(("end", kw))
        return self

    def update(self, **kw):
        self._client.calls.append(("update", kw))
        return self

    def start_observation(self, **kw):
        self._client.calls.append(("child", kw))
        return _StubSpan(self._client)


class _StubClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.events: list[dict] = []

    def start_observation(self, **kw):
        self.calls.append(("root", kw))
        return _StubSpan(self)

    def create_event(self, **kw):
        self.events.append(kw)
        return None


def _now() -> datetime:
    return datetime.now(UTC)


def _make_provider(**overrides) -> LangfuseProvider:
    obs = _StubObs()
    for k, v in overrides.items():
        setattr(obs, k, v)
    settings = type("S", (), {"observability": obs})()
    p = LangfuseProvider(settings)
    p._client = _StubClient()  # mock，跳过 initialize
    return p


def _ok_events(request_id: str = "req-1"):
    """一条完整的 ok 请求事件序列。"""
    start = _now()
    events = [
        RetrievalPhaseEvent(
            stage="understand",
            latency_ms=2.0,
            started_at=start,
            ended_at=start,
            request_id=request_id,
        ),
        RetrievalPhaseEvent(
            stage="candidate",
            latency_ms=8.0,
            candidates=10,
            started_at=start,
            ended_at=start,
            request_id=request_id,
        ),
        RetrievalPhaseEvent(
            stage="rank_filter",
            latency_ms=5.0,
            candidates=10,
            retrieved=3,
            started_at=start,
            ended_at=start,
            request_id=request_id,
        ),
        RetrievalPhaseEvent(
            stage="total",
            latency_ms=15.0,
            candidates=10,
            retrieved=3,
            started_at=start,
            ended_at=start,
            request_id=request_id,
        ),
        GenerationEvent(
            tokens={"prompt_tokens": 120, "completion_tokens": 80, "total_tokens": 200},
            model="deepseek-v3",
            latency_ms=300.0,
            started_at=start,
            ended_at=start,
            request_id=request_id,
        ),
        RagQueryEvent(
            query="退休金如何计算",
            query_len=7,
            top_k=3,
            latencies={"retrieval": 15.0, "generation": 300.0, "total": 318.0},
            tokens={"prompt_tokens": 120, "completion_tokens": 80, "total_tokens": 200},
            provider="deepseek",
            model="deepseek-v3",
            status="ok",
            error_type=None,
            started_at=start,
            ended_at=start,
            request_id=request_id,
        ),
    ]
    return events


# ---------------------------------------------------------------------------
# LangfuseProvider：归组与翻译
# ---------------------------------------------------------------------------
class TestLangfuseProvider:
    def test_full_ok_flow_builds_trace(self):
        p = _make_provider()
        for e in _ok_events():
            p.handle_event(e)

        client = p._client
        roots = [c for c in client.calls if c[0] == "root"]
        children = [c for c in client.calls if c[0] == "child"]
        assert len(roots) == 1
        assert len(children) == 2  # retrieval + generation

        root_kw = roots[0][1]
        assert root_kw["name"] == "rag_query"
        assert root_kw["as_type"] == "chain"
        assert root_kw["input"] == "退休金如何计算"
        assert root_kw["metadata"]["status"] == "ok"

        child_names = [c[1]["name"] for c in children]
        assert child_names == ["retrieval", "generation"]
        # retrieval 子 span 携带三阶段合并数据
        retrieval = children[0][1]
        assert retrieval["as_type"] == "retriever"
        assert set(retrieval["metadata"]["stages"]) == {
            "understand",
            "candidate",
            "rank_filter",
            "total",
        }
        assert retrieval["metadata"]["stages"]["candidate"]["candidates"] == 10
        # generation 子 span 携带真实用量
        gen = children[1][1]
        assert gen["as_type"] == "generation"
        assert gen["model"] == "deepseek-v3"
        assert gen["usage_details"] == {"input": 120, "output": 80, "total": 200}

    def test_empty_flow_reports_reason_no_generation(self):
        p = _make_provider()
        start = _now()
        p.handle_event(
            RetrievalPhaseEvent(
                stage="total",
                latency_ms=3.0,
                candidates=0,
                retrieved=0,
                empty_reason="no_candidate",
                started_at=start,
                ended_at=start,
                request_id="req-empty",
            )
        )
        p.handle_event(
            RagQueryEvent(
                query="不存在的问题",
                query_len=6,
                top_k=5,
                latencies={"total": 3.0},
                tokens=None,
                provider="none",
                model="none",
                status="empty",
                error_type=None,
                started_at=start,
                ended_at=start,
                request_id="req-empty",
            )
        )
        roots = [c for c in p._client.calls if c[0] == "root"]
        children = [c for c in p._client.calls if c[0] == "child"]
        assert len(roots) == 1
        assert len(children) == 1  # 只有 retrieval，无 generation
        stages = children[0][1]["metadata"]["stages"]
        assert stages["total"]["empty_reason"] == "no_candidate"

    def test_error_flow_marks_level_error(self):
        p = _make_provider()
        start = _now()
        p.handle_event(
            RagQueryEvent(
                query="x",
                query_len=1,
                top_k=3,
                latencies={"total": 5.0},
                tokens=None,
                provider="deepseek",
                model="deepseek-v3",
                status="error",
                error_type="TimeoutError",
                started_at=start,
                ended_at=start,
                request_id="req-err",
            )
        )
        updates = [c for c in p._client.calls if c[0] == "update"]
        assert updates, "error 请求应对根 span 打 ERROR"
        assert updates[-1][1]["level"] == "ERROR"

    def test_mask_query(self):
        p = _make_provider(mask_query=True)
        for e in _ok_events("req-mask"):
            p.handle_event(e)
        root_kw = p._client.calls[0][1]
        assert root_kw["input"] == "[masked]"

    def test_failure_event_creates_event(self):
        p = _make_provider()
        p.handle_event(
            FailureEvent(
                phase="retrieval",
                error_type="RuntimeError",
                message="boom",
                request_id="req-f",
            )
        )
        assert len(p._client.events) == 1
        ev = p._client.events[0]
        assert ev["name"] == "failure:retrieval"
        assert ev["level"] == "ERROR"

    def test_no_client_is_noop(self):
        p = _make_provider()
        p._client = None
        for e in _ok_events("req-x"):
            p.handle_event(e)  # 不抛异常

    def test_shutdown_clears_pending(self):
        p = _make_provider()
        start = _now()
        p.handle_event(
            RetrievalPhaseEvent(
                stage="total", latency_ms=1.0, started_at=start, ended_at=start, request_id="req-z"
            )
        )
        assert p._pending
        p.shutdown()
        assert p._pending == {}
        assert p._client is None

    def test_trace_id_valid_hex_passthrough(self):
        p = _make_provider()
        rid = "a" * 32  # 合法 32 位小写 hex
        assert p._trace_id(rid) == rid

    def test_trace_id_non_hex_maps_to_md5(self):
        p = _make_provider()
        rid = "smoke-abc123"  # 非法 trace id（连字符、长度不足）
        tid = p._trace_id(rid)
        assert len(tid) == 32 and all(c in "0123456789abcdef" for c in tid)
        assert p._trace_id(rid) == tid  # 稳定幂等

    def test_trace_id_uppercase_normalized_to_md5(self):
        p = _make_provider()
        tid = p._trace_id("ABCDEF" * 5 + "AB")  # 32 位但含大写
        assert len(tid) == 32 and all(c in "0123456789abcdef" for c in tid)


# ---------------------------------------------------------------------------
# 采样
# ---------------------------------------------------------------------------
class TestSampling:
    def test_full_rate_always_sampled(self):
        p = _make_provider(trace_sample_rate=1.0)
        assert all(p._sampled(f"req-{i}") for i in range(20))

    def test_zero_rate_never_sampled(self):
        p = _make_provider(trace_sample_rate=0.0)
        assert not any(p._sampled(f"req-{i}") for i in range(20))

    def test_half_rate_deterministic(self):
        p = _make_provider(trace_sample_rate=0.5)
        a = [p._sampled(f"req-{i}") for i in range(100)]
        b = [p._sampled(f"req-{i}") for i in range(100)]
        assert a == b  # 同一 rid 结果稳定
        assert 0 < sum(a) < 100  # 有采样也有丢弃


# ---------------------------------------------------------------------------
# 聚合器
# ---------------------------------------------------------------------------
class TestAggregator:
    def test_empty_rate_and_failures(self):
        agg = AggregatorProvider()
        now = _now()
        agg.handle_event(
            RetrievalPhaseEvent(
                stage="total",
                latency_ms=10.0,
                candidates=5,
                retrieved=3,
                started_at=now,
                ended_at=now,
            )
        )
        agg.handle_event(
            RetrievalPhaseEvent(
                stage="total",
                latency_ms=20.0,
                candidates=0,
                retrieved=0,
                empty_reason="no_candidate",
                started_at=now,
                ended_at=now,
            )
        )
        agg.handle_event(
            RagQueryEvent(
                query="x",
                query_len=1,
                top_k=3,
                latencies={"total": 15.0},
                tokens=None,
                provider="m",
                model="m2",
                status="error",
                error_type="TimeoutError",
                started_at=now,
                ended_at=now,
            )
        )
        agg.handle_event(FailureEvent(phase="query", error_type="TimeoutError", message="x"))
        snap = agg.snapshot()["window_3600s"]
        assert snap["retrieval_requests"] == 2
        assert snap["empty_retrieval"]["rate"] == 0.5
        assert snap["empty_retrieval"]["reasons"]["no_candidate"] == 1
        assert snap["failures"]["total"] == 1
        assert snap["failures"]["by_phase"]["query"] == 1
        assert snap["retrieval_latency_ms"]["p50"] == 15.0

    def test_empty_retrieval_agg_count_ok(self):
        agg = AggregatorProvider()
        now = _now()
        for i in range(3):
            agg.handle_event(
                RetrievalPhaseEvent(
                    stage="total",
                    latency_ms=float(i + 1),
                    candidates=0,
                    retrieved=0,
                    empty_reason="filtered_out",
                    started_at=now,
                    ended_at=now,
                )
            )
        snap = agg.snapshot()["window_3600s"]
        assert snap["retrieval_requests"] == 3
        assert snap["empty_retrieval"]["total"] == 3
        assert snap["empty_retrieval"]["rate"] == 1.0
        assert snap["retrieved_docs"]["mean"] == 0.0


# ---------------------------------------------------------------------------
# Manager：request_id 注入与 Provider 异常隔离
# ---------------------------------------------------------------------------
class _BoomProvider(ObservabilityProvider):
    name = "boom"

    def handle_event(self, event: ObservabilityEvent) -> None:
        raise RuntimeError("provider exploded")


class TestManagerIsolation:
    def test_request_id_injected_from_contextvar(self):
        m = manager.__class__()
        seen: list[str] = []

        class _Recorder(ObservabilityProvider):
            name = "recorder"

            def handle_event(self, event: ObservabilityEvent) -> None:
                seen.append(event.request_id)

        m._enabled = True
        m.register(_Recorder())
        token = set_request_id("req-ctx-1")
        try:
            m.emit(
                RetrievalPhaseEvent(
                    stage="total", latency_ms=1.0, started_at=_now(), ended_at=_now()
                )
            )
        finally:
            reset_request_id(token)
        assert seen == ["req-ctx-1"]

    def test_provider_exception_isolated(self):
        m = manager.__class__()
        m._enabled = True
        m.register(_BoomProvider())
        # 不应抛异常
        m.emit(
            RetrievalPhaseEvent(stage="total", latency_ms=1.0, started_at=_now(), ended_at=_now())
        )

    def test_disabled_manager_skips(self):
        m = manager.__class__()
        hit = []

        class _R(ObservabilityProvider):
            name = "r"

            def handle_event(self, event: ObservabilityEvent) -> None:
                hit.append(1)

        m.register(_R())
        m.emit(
            RetrievalPhaseEvent(stage="total", latency_ms=1.0, started_at=_now(), ended_at=_now())
        )
        assert hit == []
