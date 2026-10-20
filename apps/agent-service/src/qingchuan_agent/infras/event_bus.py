#!/usr/bin/env python3
"""事件总线（晴川 x-QingChuan）。

骨架阶段提供进程内内存实现（InMemoryEventBus），保证 Agent 协作事件
「落库留痕 + 广播」双写链路可跑通；生产环境切换 Redis Stream 实现时，
替换工厂函数即可，业务层不感知（对齐 DatabaseProvider 的抽象口径）。

TODO: redis 实现（RedisConfig 接入后按 Stream / PubSub 落地）。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from qingchuan_agent.core.logger import logger


@dataclass(frozen=True)
class EventMessage:
    """事件总线消息载体。"""

    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    source_agent: str | None = None
    target_agent: str | None = None


class EventBus(ABC):
    """事件总线抽象接口。"""

    @abstractmethod
    async def publish(self, message: EventMessage) -> None:
        """发布一条事件消息。"""

    @abstractmethod
    async def subscribe(self, callback: Any) -> None:
        """订阅事件（callback 异步接收 EventMessage）。"""


class InMemoryEventBus(EventBus):
    """内存事件总线（单进程内广播；重启即失，仅骨架/开发期）。"""

    def __init__(self) -> None:
        self._subscribers: list[Any] = []

    async def publish(self, message: EventMessage) -> None:
        logger.info(f"[EventBus] publish type={message.event_type} source={message.source_agent}")
        for callback in list(self._subscribers):
            try:
                await callback(message)
            except Exception as exc:  # 订阅者异常不影响发布主流程
                logger.exception(f"[EventBus] subscriber error: {exc}")

    async def subscribe(self, callback: Any) -> None:
        self._subscribers.append(callback)
        logger.info(f"[EventBus] subscriber 已登记：{callback}")


# 模块级单例
_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """获取全局事件总线单例（骨架：内存实现）。"""
    global _event_bus
    if _event_bus is None:
        _event_bus = InMemoryEventBus()
    return _event_bus


__all__ = ["EventBus", "EventMessage", "InMemoryEventBus", "get_event_bus"]
