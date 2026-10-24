"""事件总线测试：InMemory 语义 + Redis Pub/Sub 往返 + 工厂切换。"""

import asyncio
import json
import uuid

import pytest
from qingchuan_agent.infras.event_bus import (
    EventMessage,
    InMemoryEventBus,
    RedisEventBus,
    _decode_message,
)


@pytest.mark.asyncio
async def test_in_memory_publish_subscribe():
    """InMemory：发布后订阅回调同步收到消息。"""
    bus = InMemoryEventBus()
    received: list[EventMessage] = []

    async def callback(message: EventMessage) -> None:
        received.append(message)

    await bus.subscribe(callback)
    await bus.publish(
        EventMessage(
            event_type="agent.task.completed",
            payload={"task_id": 1},
            source_agent="customer_service",
            target_agent="agent_b",
        )
    )
    assert len(received) == 1
    assert received[0].event_type == "agent.task.completed"
    assert received[0].payload == {"task_id": 1}
    assert received[0].source_agent == "customer_service"
    assert received[0].target_agent == "agent_b"


@pytest.mark.asyncio
async def test_in_memory_subscriber_error_not_blocking():
    """InMemory：订阅者抛异常不影响其他订阅者与发布主流程。"""
    bus = InMemoryEventBus()
    received: list[str] = []

    async def bad_callback(message: EventMessage) -> None:
        raise RuntimeError("boom")

    async def good_callback(message: EventMessage) -> None:
        received.append(message.event_type)

    await bus.subscribe(bad_callback)
    await bus.subscribe(good_callback)
    await bus.publish(EventMessage(event_type="ok"))
    assert received == ["ok"]


@pytest.mark.asyncio
async def test_in_memory_unsubscribe():
    """InMemory：unsubscribe 后回调不再收到事件（SSE 断开清理场景）。"""
    bus = InMemoryEventBus()
    received: list[str] = []

    async def callback(message: EventMessage) -> None:
        received.append(message.event_type)

    await bus.subscribe(callback)
    await bus.publish(EventMessage(event_type="before"))
    assert received == ["before"]

    await bus.unsubscribe(callback)
    await bus.publish(EventMessage(event_type="after"))
    assert received == ["before"]  # 注销后不再追加


def test_decode_message_roundtrip():
    """消息反序列化：合法 JSON → EventMessage；脏数据丢弃。"""
    raw = json.dumps(
        {
            "event_type": "agent.started",
            "payload": {"task_id": 42},
            "source_agent": "route",
            "target_agent": None,
        },
        ensure_ascii=False,
    )
    msg = _decode_message(raw)
    assert msg is not None
    assert msg.event_type == "agent.started"
    assert msg.payload == {"task_id": 42}
    assert msg.source_agent == "route"

    assert _decode_message(b"not-json") is None
    assert _decode_message("") is None
    assert _decode_message(None) is None


def test_get_event_bus_factory_default_in_memory():
    """工厂：redis 未启用时返回 InMemoryEventBus。"""
    import qingchuan_agent.infras.event_bus as event_bus_module
    from qingchuan_agent.core.config import get_settings

    assert get_settings().redis.enabled is False
    event_bus_module._event_bus = None
    try:
        bus = event_bus_module.get_event_bus()
        assert isinstance(bus, InMemoryEventBus)
    finally:
        event_bus_module._event_bus = None


@pytest.mark.asyncio
async def test_redis_event_bus_roundtrip():
    """Redis Pub/Sub 往返：publish 后订阅回调收到（本地 Redis 不可用时跳过）。"""
    import redis.asyncio as aioredis
    from qingchuan_agent.core.config import get_settings

    settings = get_settings()
    # 密码置于 userinfo 前：redis://:password@host:port/db
    auth = f":{settings.redis.password}@" if settings.redis.password else ""
    client = aioredis.from_url(
        f"redis://{auth}localhost:6379/15",
        decode_responses=True,
        socket_timeout=3,
    )
    try:
        await client.ping()
    except Exception:
        await client.aclose()
        pytest.skip("本地 Redis 不可用（未配置 QINGCHUAN_AGENT_REDIS_PASSWORD），跳过往返测试")

    channel = f"qingchuan:test:{uuid.uuid4().hex[:8]}"
    bus = RedisEventBus(client=client, channel=channel)
    received: list[EventMessage] = []

    async def callback(message: EventMessage) -> None:
        received.append(message)

    try:
        await bus.subscribe(callback)
        await asyncio.sleep(0.3)  # 等待订阅循环就绪
        await bus.publish(
            EventMessage(
                event_type="agent.task.completed",
                payload={"task_id": 7},
                source_agent="customer_service",
            )
        )
        for _ in range(50):
            if received:
                break
            await asyncio.sleep(0.1)
        assert len(received) == 1
        assert received[0].event_type == "agent.task.completed"
        assert received[0].payload == {"task_id": 7}
        assert received[0].source_agent == "customer_service"
    finally:
        await bus.stop()
        await client.aclose()
