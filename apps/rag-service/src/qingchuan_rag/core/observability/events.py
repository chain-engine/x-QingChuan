"""可观测性事件模型（事件驱动：埋点只发事件，Provider 翻译成自己的形态）。

设计原则：
- 埋点代码不感知后端（Langfuse / Prometheus / 日志），只构造并 emit 事件；
- 事件携带足够信息（耗时、数量、时间戳），各 Provider 按需取用；
- request_id 由 manager.emit() 自动补齐（来自 ContextVar），埋点处无需关心；
- 基类 ObservabilityEvent 非 dataclass（避免字段顺序约束），子类自行声明字段。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ObservabilityEvent:
    """事件基类：仅类型标记与 kind。"""

    kind: str = "base"


@dataclass
class RetrievalPhaseEvent(ObservabilityEvent):
    """检索阶段事件（每阶段一条：understand / candidate / rank_filter / total）。

    - latency_ms: 本阶段耗时
    - candidates: 候选召回数（stage2 输出）
    - retrieved:  最终召回数（stage3 输出）
    - empty_reason: 空召回原因（no_candidate=无候选 / filtered_out=被阈值过滤杀光），None 表示非空
    """

    stage: str
    latency_ms: float
    started_at: datetime = field(default_factory=_utcnow)
    ended_at: datetime = field(default_factory=_utcnow)
    candidates: int = 0
    retrieved: int = 0
    empty_reason: str | None = None
    request_id: str | None = None

    def __post_init__(self) -> None:
        self.kind = "retrieval_phase"


@dataclass
class GenerationEvent(ObservabilityEvent):
    """生成事件（LLM 调用完成后一条）。

    - tokens: {prompt_tokens, completion_tokens, total_tokens} 或 None（模型未返回用量）
    - model: 实际使用的模型名
    """

    tokens: dict | None
    model: str
    latency_ms: float
    started_at: datetime = field(default_factory=_utcnow)
    ended_at: datetime = field(default_factory=_utcnow)
    request_id: str | None = None

    def __post_init__(self) -> None:
        self.kind = "generation"


@dataclass
class RagQueryEvent(ObservabilityEvent):
    """RAG 查询总览事件（一次 /rag/query 或内部 query 完成后一条）。

    - latencies: {retrieval, augmentation, generation, total} 单位 ms
    - tokens: 生成 tokens（与 GenerationEvent 一致）；空召回时为 None
    - status: ok / empty（空召回）/ error（异常）
    - query: 原始问题文本（Langfuse trace 的 input；mask_query=true 时由 Provider 脱敏）
    """

    query: str
    query_len: int
    top_k: int
    latencies: dict
    tokens: dict | None
    provider: str
    model: str
    status: str
    error_type: str | None
    started_at: datetime = field(default_factory=_utcnow)
    ended_at: datetime = field(default_factory=_utcnow)
    request_id: str | None = None

    def __post_init__(self) -> None:
        self.kind = "rag_query"


@dataclass
class HttpRequestEvent(ObservabilityEvent):
    """HTTP 请求事件（中间件层，每请求一条）。

    - status_class: 2xx / 4xx / 5xx（失败率的分母与分子来源之一）
    - latency_ms: 整请求耗时
    """

    endpoint: str
    status_class: str
    latency_ms: float
    request_id: str | None = None

    def __post_init__(self) -> None:
        self.kind = "http_request"


@dataclass
class FailureEvent(ObservabilityEvent):
    """失败事件（业务阶段失败：检索 / 生成 / 全链路 / HTTP）。

    - phase: retrieval / generation / http / full
    - error_type: 异常类型名（如 RetrievalError / GenerationError）
    """

    phase: str
    error_type: str
    message: str | None = None
    request_id: str | None = None

    def __post_init__(self) -> None:
        self.kind = "failure"


__all__ = [
    "ObservabilityEvent",
    "RetrievalPhaseEvent",
    "GenerationEvent",
    "RagQueryEvent",
    "HttpRequestEvent",
    "FailureEvent",
]
