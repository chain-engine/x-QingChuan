"""Redis Stream 任务队列与 Worker 测试。

- TaskStreamQueue：enqueue → dequeue → ack 往返（真 Redis，db 15 隔离；不可用跳过）
- TaskWorker：消费 submit 消息 → 调 AgentRuntime → 回写任务 → 发布 task.state 事件
"""

import pytest
from qingchuan_agent.agents.runtime import AgentRuntime
from qingchuan_agent.infras.event_bus import EventMessage, InMemoryEventBus
from qingchuan_agent.infras.task_stream import TASK_STREAM, TaskStreamQueue
from qingchuan_agent.models.entities.agent_task import AgentTask
from qingchuan_agent.services.task_worker import TASK_STATE_EVENT, TaskWorker


def _redis_client():
    import redis.asyncio as aioredis
    from qingchuan_agent.core.config import get_settings

    settings = get_settings()
    auth = f":{settings.redis.password}@" if settings.redis.password else ""
    return aioredis.from_url(
        f"redis://{auth}localhost:6379/15",
        decode_responses=True,
        socket_timeout=3,
    )


async def _fresh_queue() -> TaskStreamQueue:
    client = _redis_client()
    try:
        await client.ping()
    except Exception:
        await client.aclose()
        pytest.skip("本地 Redis 不可用，跳过任务队列集成测试")
    await client.delete(TASK_STREAM)
    queue = TaskStreamQueue(client=client)
    await queue.ensure_group()
    return queue


class _FakeRuntime(AgentRuntime):
    """记录调用参数的替身 runtime，返回固定最终状态。"""

    def __init__(self) -> None:
        self.invoked: dict | None = None

    def invoke_task(self, **kwargs) -> dict:
        self.invoked = kwargs
        return {
            "status": "success",
            "result": {"answer": "ok"},
            "target_agent": "content",
            "error": None,
            "events": [],
        }


class _FakeSession:
    """worker 用极简会话替身：get 返回预置任务，add 收集对象，commit 无操作。"""

    def __init__(self, task: AgentTask) -> None:
        self.task = task
        self.added: list = []

    def get(self, model_class, model_id):
        if isinstance(self.task, model_class) and self.task.id == int(model_id):
            return self.task
        return None

    def add(self, model) -> None:
        self.added.append(model)

    def commit(self) -> None:
        pass

    def close(self) -> None:
        pass


@pytest.mark.asyncio
async def test_task_stream_queue_roundtrip():
    """队列往返：enqueue → dequeue 拉回原字段 → ack 后无新消息。"""
    queue = await _fresh_queue()
    try:
        msg_id = await queue.enqueue(
            {"action": "submit", "task_id": 42, "task_type": "content", "thread_id": "task:42"}
        )
        assert msg_id
        assert await queue.pending_count() == 1

        messages = await queue.dequeue(block_ms=1000)
        assert len(messages) == 1
        mid, fields = messages[0]
        assert mid == msg_id
        assert fields["action"] == "submit"
        assert int(fields["task_id"]) == 42
        assert fields["task_type"] == "content"

        await queue.ack(mid)
        # 已确认的消息不再投递给消费者
        assert await queue.dequeue(block_ms=100) == []
    finally:
        await queue._client.aclose()


@pytest.mark.asyncio
async def test_task_stream_enqueue_payload_json_roundtrip():
    """dict payload 经 JSON 序列化后还原（Stream 字段须 flat scalar）。"""
    queue = await _fresh_queue()
    try:
        await queue.enqueue(
            {
                "action": "submit",
                "task_id": 7,
                "thread_id": "task:7",
                "payload": {"query": "你好", "nested": {"a": [1, 2]}},
            }
        )
        messages = await queue.dequeue(block_ms=1000)
        assert len(messages) == 1
        _, fields = messages[0]
        assert fields["payload"] == {"query": "你好", "nested": {"a": [1, 2]}}
        await queue.ack(messages[0][0])
    finally:
        await queue._client.aclose()


@pytest.mark.asyncio
async def test_task_worker_process_submit():
    """worker 消费 submit：调 runtime、回写任务、发布 task.state 事件。"""
    queue = await _fresh_queue()
    bus = InMemoryEventBus()
    runtime = _FakeRuntime()
    task = AgentTask(id=99, task_type="content", payload={"query": "x"})
    received: list[EventMessage] = []
    await bus.subscribe(lambda m: received.append(m))

    session = _FakeSession(task)
    worker = TaskWorker(
        queue=queue,
        session_factory=lambda: session,
        runtime=runtime,
        event_bus=bus,
    )
    try:
        await queue.enqueue(
            {"action": "submit", "task_id": 99, "task_type": "content", "thread_id": "task:99"}
        )
        messages = await queue.dequeue(block_ms=1000)
        assert len(messages) == 1
        await worker._process(messages[0][1])

        # runtime 被调用且任务回写
        assert runtime.invoked is not None
        assert runtime.invoked["task_type"] == "content"
        assert runtime.invoked["task_id"] == 99
        assert task.status == "success"
        assert task.assignee_agent == "content"

        # task.state 事件（running + success）落库并发布
        state_events = [e for e in session.added if e.event_type == TASK_STATE_EVENT]
        assert len(state_events) == 2
        assert [e.payload["status"] for e in state_events] == ["running", "success"]
        assert any(m.event_type == TASK_STATE_EVENT for m in received)
        assert any(m.payload.get("status") == "success" for m in received)
    finally:
        await queue._client.aclose()
