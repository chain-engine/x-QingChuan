"""observability 包：事件总线 + Provider 插件化 + 本地聚合。

对外入口：
    from qingchuan_rag.core.observability import emit
    from qingchuan_rag.core.observability.events import RetrievalPhaseEvent
    emit(RetrievalPhaseEvent(stage="understand", latency_ms=12.3))
"""

from qingchuan_rag.core.observability.base import ObservabilityProvider
from qingchuan_rag.core.observability.manager import (
    ObservabilityManager,
    emit,
    get_request_id,
    manager,
    reset_request_id,
    set_request_id,
)

__all__ = [
    "ObservabilityProvider",
    "ObservabilityManager",
    "manager",
    "emit",
    "set_request_id",
    "reset_request_id",
    "get_request_id",
]
