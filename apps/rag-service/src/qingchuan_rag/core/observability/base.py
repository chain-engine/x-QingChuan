"""可观测性 Provider 抽象基类（插件化扩展点）。

接入新平台 = 实现本基类的 handle_event，并注册进 ObservabilityManager：
    class PrometheusProvider(ObservabilityProvider):
        name = "prometheus"
        def handle_event(self, event): ...

埋点代码零改动。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from qingchuan_rag.core.observability.events import ObservabilityEvent


class ObservabilityProvider(ABC):
    """观测平台 Provider 基类。"""

    name: ClassVar[str] = "base"

    def initialize(self) -> None:
        """初始化（可选覆写；失败不应阻断业务启动，由 Manager 捕获）。"""
        return None

    @abstractmethod
    def handle_event(self, event: ObservabilityEvent) -> None:
        """处理一个观测事件（翻译成自身形态）。实现必须不抛异常（Manager 也会兜底）。"""

    def shutdown(self) -> None:
        """关闭（可选覆写）。"""
        return None


__all__ = ["ObservabilityProvider"]
