#!/usr/bin/env python3
"""事件总线（晴川 x-QingChuan）。

两种实现，业务层只依赖 EventBus 抽象（publish / subscribe）：
    - InMemoryEventBus：进程内广播（骨架 / 开发期；单进程内闭环，重启即失）
    - RedisEventBus：Redis Pub/Sub 跨进程广播（生产多副本 / 多 worker 实时通知；
      与 checkpoint 共用同一 Redis 实例配置，分别持有异步连接）

工厂按 QINGCHUAN_AGENT_REDIS_ENABLED + 连接探测结果切换实现；
Redis 未启用 / 不可用时静默回退内存实现（不阻断业务）。
事件消息仍走 agent_events 落库留痕（services 层双写），总线只承担实时广播。
"""

from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any

from qingchuan_agent.core.config import get_settings
from qingchuan_agent.core.logger import logger

# Redis 广播频道（事件总线专用）
DEFAULT_CHANNEL: str = "qingchuan:agent:events"


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


class RedisEventBus(EventBus):
    """Redis Pub/Sub 事件总线（跨进程广播；生产多副本实时通知）。

    连接与 checkpoint 共用同一 Redis 实例（同一 QINGCHUAN_AGENT_REDIS_* 配置），
    此处使用异步连接（redis.asyncio）；订阅循环惰性启动（首次 subscribe 时）。
    """

    def __init__(
        self,
        client: Any | None = None,
        channel: str = DEFAULT_CHANNEL,
    ) -> None:
        from qingchuan_agent.infras.redis_client import get_async_redis_client

        self._client = client if client is not None else get_async_redis_client()
        self._channel = channel
        self._subscribers: list[Any] = []
        self._pubsub: Any | None = None
        self._task: asyncio.Task | None = None

    async def publish(self, message: EventMessage) -> None:
        try:
            payload = json.dumps(asdict(message), ensure_ascii=False)
            await self._client.publish(self._channel, payload)
            logger.info(
                f"[EventBus] publish type={message.event_type} "
                f"source={message.source_agent}"
            )
        except Exception as exc:  # 总线异常不阻断业务（事件已落库留痕）
            logger.warning(f"[EventBus] Redis publish failed: {exc}")

    async def subscribe(self, callback: Any) -> None:
        self._subscribers.append(callback)
        logger.info(f"[EventBus] subscriber 已登记：{callback}")
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run_loop())
            logger.info(f"[EventBus] Redis 订阅循环启动：channel={self._channel}")

    async def _run_loop(self) -> None:
        self._pubsub = self._client.pubsub()
        try:
            await self._pubsub.subscribe(self._channel)
            while True:
                raw = await self._pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if raw is None:
                    continue
                message = _decode_message(raw.get("data"))
                if message is None:
                    continue
                for callback in list(self._subscribers):
                    try:
                        await callback(message)
                    except Exception as exc:
                        logger.exception(f"[EventBus] subscriber error: {exc}")
        except asyncio.CancelledError:
            logger.info("[EventBus] Redis 订阅循环已停止")
        except Exception as exc:
            logger.warning(f"[EventBus] Redis 订阅循环异常退出：{exc}")
        finally:
            try:
                if self._pubsub is not None:
                    await self._pubsub.unsubscribe(self._channel)
                    await self._pubsub.close()
            except Exception as exc:
                logger.warning(f"[EventBus] 关闭 pubsub 异常：{exc}")
            self._pubsub = None

    async def stop(self) -> None:
        """停止订阅循环并释放 pubsub（lifespan 关闭阶段调用；幂等）。"""
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None
        self._subscribers.clear()
        logger.info("[EventBus] Redis 事件总线已停止")


def _decode_message(data: Any) -> EventMessage | None:
    """反序列化 Redis 消息 → EventMessage（脏数据告警并丢弃）。"""
    if isinstance(data, bytes):
        data = data.decode("utf-8", errors="replace")
    if not isinstance(data, str) or not data:
        return None
    try:
        obj = json.loads(data)
        return EventMessage(
            event_type=obj.get("event_type", ""),
            payload=obj.get("payload", {}),
            source_agent=obj.get("source_agent"),
            target_agent=obj.get("target_agent"),
        )
    except (ValueError, TypeError) as exc:
        logger.warning(f"[EventBus] 消息反序列化失败，丢弃：{exc}")
        return None


# 模块级单例
_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """获取全局事件总线单例（按 Redis 可用性选择实现）。"""
    global _event_bus
    if _event_bus is None:
        from qingchuan_agent.infras.redis_client import redis_available

        if get_settings().redis.enabled and redis_available():
            _event_bus = RedisEventBus()
            logger.info("EventBus 实现：Redis Pub/Sub（跨进程广播）")
        else:
            _event_bus = InMemoryEventBus()
            logger.info("EventBus 实现：InMemory（单进程广播）")
    return _event_bus


async def shutdown_event_bus() -> None:
    """关闭全局事件总线（lifespan 关闭阶段调用；幂等）。"""
    global _event_bus
    bus = _event_bus
    _event_bus = None
    if isinstance(bus, RedisEventBus):
        await bus.stop()


__all__ = [
    "DEFAULT_CHANNEL",
    "EventBus",
    "EventMessage",
    "InMemoryEventBus",
    "RedisEventBus",
    "get_event_bus",
    "shutdown_event_bus",
]
