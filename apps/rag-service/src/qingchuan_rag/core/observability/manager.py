"""ObservabilityManager：事件总线 + Provider 注册/分发。

- emit(event)：把事件分发给所有已注册 Provider，逐个 try/except 隔离；
- 业务零阻断：任何 Provider 异常只记 warn，绝不影响 RAG 主链路；
- request_id 自动补齐（来自 contextvar，由 middleware 注入）。
"""

from __future__ import annotations

import contextvars
from typing import Any

from qingchuan_rag.core.logger import logger
from qingchuan_rag.core.observability.base import ObservabilityProvider
from qingchuan_rag.core.observability.events import ObservabilityEvent

# 当前请求 ID（middleware 注入；非 HTTP 场景（CLI/离线）为 None）
_request_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "qingchuan_obs_request_id", default=None
)


def set_request_id(request_id: str | None) -> contextvars.Token | None:
    """在请求作用域内设置 request_id（middleware 调用）。返回 token 供 reset。"""
    return _request_id_ctx.set(request_id)


def reset_request_id(token: contextvars.Token | None) -> None:
    """恢复 request_id（middleware 退出时调用）。"""
    if token is not None:
        _request_id_ctx.reset(token)


def get_request_id() -> str | None:
    return _request_id_ctx.get()


class ObservabilityManager:
    """观测事件分发器。"""

    def __init__(self) -> None:
        self._providers: list[ObservabilityProvider] = []
        self._initialized: bool = False
        self._enabled: bool = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def providers(self) -> list[ObservabilityProvider]:
        return list(self._providers)

    def initialize(self, settings: Any) -> None:
        """按配置初始化 Provider。

        - enabled=False 时整体关闭（零开销）；
        - LoggingProvider 兜底恒注册（日志通道永不缺席）；
        - providers 列表指定附加平台（如 langfuse），缺失依赖/配置时跳过并告警。
        """
        if self._initialized:
            return
        self._enabled = bool(settings.observability.enabled)

        from qingchuan_rag.core.observability.aggregator import AggregatorProvider
        from qingchuan_rag.core.observability.providers.logging_provider import LoggingProvider

        if not self._enabled:
            self._initialized = True
            return

        # 聚合器：率/分布指标（空召回率、失败率、P50/P95）→ /obs/stats
        self.register(AggregatorProvider())
        # 日志兜底：永远注册
        self.register(LoggingProvider())

        # 附加平台（默认 langfuse；可扩展其它 Provider）
        for name in settings.observability.providers:
            if name == "langfuse":
                try:
                    from qingchuan_rag.core.observability.providers.langfuse_provider import (
                        LangfuseProvider,
                    )

                    self.register(LangfuseProvider(settings))
                except Exception as e:  # noqa: BLE001 - 平台缺失不应阻断启动
                    logger.warning(f"Observability: LangfuseProvider 不可用，已跳过: {e}")
            else:
                logger.warning(f"Observability: 未注册的 provider 名称: {name}")

        for provider in self._providers:
            try:
                provider.initialize()
            except Exception as e:  # noqa: BLE001 - Provider 初始化失败不阻断业务
                logger.warning(f"Observability: {provider.name} initialize 失败: {e}")

        self._initialized = True
        logger.info(
            f"Observability initialized: enabled={self._enabled}, "
            f"providers={[p.name for p in self._providers]}"
        )

    def register(self, provider: ObservabilityProvider) -> None:
        """注册 Provider（幂等：同名不重复注册）。"""
        if any(p.name == provider.name for p in self._providers):
            return
        self._providers.append(provider)

    def emit(self, event: ObservabilityEvent) -> None:
        """分发事件给所有 Provider。任何异常都被隔离（业务零阻断）。"""
        if not self._enabled:
            return
        if event.request_id is None:
            event.request_id = get_request_id()
        for provider in self._providers:
            try:
                provider.handle_event(event)
            except Exception as e:  # noqa: BLE001 - Provider 异常绝不影响业务
                logger.warning(f"Observability: {provider.name} handle_event 失败: {e}")

    def shutdown(self) -> None:
        for provider in self._providers:
            try:
                provider.shutdown()
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Observability: {provider.name} shutdown 失败: {e}")
        self._providers.clear()
        self._initialized = False


# 全局单例（模块级，供埋点处直接 emit）
manager = ObservabilityManager()


def emit(event: ObservabilityEvent) -> None:
    """便捷入口：emit(RetrievalPhaseEvent(...))。"""
    manager.emit(event)


__all__ = [
    "ObservabilityManager",
    "manager",
    "emit",
    "set_request_id",
    "reset_request_id",
    "get_request_id",
]
