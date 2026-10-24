#!/usr/bin/env python3
"""Redis Stream 任务队列（晴川 x-QingChuan agent-service）。

用 Redis Stream + 消费者组替代线程池执行 Agent 任务：
    - 提交任务：落库后 XADD 入队，接口立即返回（异步化）
    - worker 消费：XREADGROUP（消费者组，支持多副本分摊）
    - 失败重投：pending 超时由其它消费者认领（未配置 CLAIM 的简化版，
      生产可基于 XAUTOCLAIM 增强）

消息字段（Redis Stream 要求 flat scalar）：
    action    submit | resume
    task_id   int
    task_type str
    thread_id str
    decision / remark / extra  resume 专用（extra 为 JSON 字符串）
"""

from __future__ import annotations

import json
from typing import Any

from qingchuan_agent.core.logger import logger

# 队列与消费者组（单实例命名；如需按环境隔离可加前缀）
TASK_STREAM: str = "qingchuan:agent:tasks"
TASK_GROUP: str = "task-workers"
DEFAULT_CONSUMER: str = "worker:main"

# 单次拉取消息数与阻塞时长（毫秒）
DEQUEUE_COUNT: int = 1
BLOCK_MS: int = 5000


class TaskStreamError(RuntimeError):
    """任务队列异常（入队 / 消费 / 组初始化失败）。"""


class TaskStreamQueue:
    """Redis Stream 队列门面（持有异步 Redis 客户端）。"""

    def __init__(self, client: Any, stream: str = TASK_STREAM, group: str = TASK_GROUP) -> None:
        self._client = client
        self._stream = stream
        self._group = group

    @property
    def stream(self) -> str:
        return self._stream

    async def ensure_group(self) -> None:
        """创建消费者组（幂等；已存在时忽略 BUSYGROUP）。"""
        try:
            await self._client.xgroup_create(
                name=self._stream, groupname=self._group, id="0", mkstream=True
            )
            logger.info(f"[TaskStream] 消费者组就绪：{self._stream} / {self._group}")
        except Exception as exc:
            # BUSYGROUP 属预期（组已存在），其余异常抛出由调用方降级
            if "BUSYGROUP" in str(exc):
                return
            raise TaskStreamError(f"初始化任务队列消费者组失败: {exc}") from exc

    async def enqueue(self, message: dict[str, Any]) -> str:
        """入队一条任务消息，返回消息 ID。"""
        fields: dict[str, str | int] = {}
        for key, value in message.items():
            if value is None:
                continue
            if isinstance(value, (dict, list)):
                fields[key] = json.dumps(value, ensure_ascii=False)
            elif isinstance(value, bool):
                fields[key] = int(value)
            else:
                fields[key] = value
        try:
            msg_id = await self._client.xadd(name=self._stream, fields=fields)
            logger.info(
                f"[TaskStream] 入队：id={fields.get('task_id')} "
                f"action={fields.get('action')} msg_id={msg_id}"
            )
            return str(msg_id)
        except Exception as exc:
            raise TaskStreamError(f"任务入队失败: {exc}") from exc

    async def dequeue(
        self, consumer: str = DEFAULT_CONSUMER, count: int = DEQUEUE_COUNT, block_ms: int = BLOCK_MS
    ) -> list[tuple[str, dict[str, Any]]]:
        """阻塞消费一条消息，返回 [(msg_id, fields)]；无消息返回 []。"""
        try:
            raw = await self._client.xreadgroup(
                groupname=self._group,
                consumername=consumer,
                streams={self._stream: ">"},
                count=count,
                block=block_ms,
            )
        except Exception as exc:
            # 连接抖动：告警并返回空，由调用方继续循环（不中断 worker）
            logger.warning(f"[TaskStream] 消费异常：{exc}")
            return []
        if not raw:
            return []
        items: list[tuple[str, dict[str, Any]]] = []
        for _stream_name, entries in raw:
            for msg_id, fields in entries:
                items.append((str(msg_id), self._decode_fields(fields)))
        return items

    async def ack(self, msg_id: str) -> None:
        """确认消息已处理（防止重复执行）。"""
        try:
            await self._client.xack(self._stream, self._group, msg_id)
        except Exception as exc:
            logger.warning(f"[TaskStream] ACK 失败（{msg_id}）：{exc}")

    async def pending_count(self) -> int:
        """队列长度（待处理消息数）。"""
        try:
            length = await self._client.xlen(self._stream)
            return int(length)
        except Exception as exc:
            logger.warning(f"[TaskStream] 队列长度查询失败：{exc}")
            return 0

    @staticmethod
    def _decode_fields(fields: dict[Any, Any]) -> dict[str, Any]:
        """Stream 字段反序列化：JSON 串还原为 dict/list，其余保留。"""
        out: dict[str, Any] = {}
        for key, value in fields.items():
            k = str(key)
            v = value.decode("utf-8") if isinstance(value, bytes) else value
            if k in ("extra", "payload") and isinstance(v, str):
                try:
                    out[k] = json.loads(v)
                    continue
                except (ValueError, TypeError):
                    pass
            out[k] = v
        return out


# 模块级单例（按 Redis 可用性装配；测试可注入替身）
_task_queue: TaskStreamQueue | None = None


def get_task_queue() -> TaskStreamQueue | None:
    """获取全局任务队列（Redis 未启用 / 不可用时返回 None → 服务走同步回退）。"""
    global _task_queue
    if _task_queue is None:
        from qingchuan_agent.core.config import get_settings
        from qingchuan_agent.infras.redis import get_async_redis_client, redis_available

        settings = get_settings()
        if settings.redis.enabled and redis_available():
            _task_queue = TaskStreamQueue(client=get_async_redis_client())
            logger.info("TaskStream 任务队列：Redis Stream（异步执行）")
    return _task_queue


def reset_task_queue() -> None:
    """重置任务队列单例（测试隔离用）。"""
    global _task_queue
    _task_queue = None


__all__ = [
    "BLOCK_MS",
    "DEFAULT_CONSUMER",
    "DEQUEUE_COUNT",
    "TASK_GROUP",
    "TASK_STREAM",
    "TaskStreamError",
    "TaskStreamQueue",
    "get_task_queue",
    "reset_task_queue",
]
