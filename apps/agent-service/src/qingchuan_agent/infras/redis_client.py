#!/usr/bin/env python3
"""Redis 连接设施（晴川 x-QingChuan agent-service）。

checkpoint 与事件总线共用同一 Redis 实例（同一连接配置 / 同一 db），
按客户端模型分持连接池：

    - 同步连接（redis.Redis）：LangGraph RedisSaver（runtime 为同步 invoke）
    - 异步连接（redis.asyncio.Redis）：事件总线 publish / subscribe

生命周期由 main.py lifespan 统一管理（init_redis → 使用 → close_redis）：
连接探测失败不阻断启动，业务侧（checkpoint / 事件总线工厂）降级到
内存实现并告警。
"""

from __future__ import annotations

import redis
import redis.asyncio as aioredis

from qingchuan_agent.core.config import get_settings
from qingchuan_agent.core.logger import logger

# 模块级单例（应用级：checkpoint / 事件总线共用同一实例配置）
_sync_client: redis.Redis | None = None
_async_client: aioredis.Redis | None = None
# 最近一次连接探测结果（False = 未启用 / 不可用，业务侧据此降级）
_available: bool = False


def get_sync_redis_client() -> redis.Redis:
    """获取同步 Redis 客户端（LangGraph RedisSaver 用；decode_responses=False 保二进制）。"""
    global _sync_client
    if _sync_client is None:
        settings = get_settings().redis
        _sync_client = redis.Redis.from_url(
            settings.connection_url,
            socket_timeout=settings.socket_timeout,
            socket_connect_timeout=settings.socket_timeout,
            decode_responses=False,
        )
    return _sync_client


def get_async_redis_client() -> aioredis.Redis:
    """获取异步 Redis 客户端（事件总线用；decode_responses=True 收 JSON 字符串）。"""
    global _async_client
    if _async_client is None:
        settings = get_settings().redis
        _async_client = aioredis.from_url(
            settings.connection_url,
            socket_timeout=settings.socket_timeout,
            socket_connect_timeout=settings.socket_timeout,
            decode_responses=True,
        )
    return _async_client


def redis_available() -> bool:
    """Redis 是否可用（init_redis 探测结果；未调用时视为不可用）。"""
    return _available


async def init_redis() -> bool:
    """初始化并探测 Redis 连接（同步 + 异步双客户端 ping）。

    - QINGCHUAN_AGENT_REDIS_ENABLED=false：直接标记不可用，返回 False；
    - 连接失败：告警并标记不可用（不抛异常，调用方降级内存实现）。

    Returns:
        bool: Redis 是否可用
    """
    global _available
    settings = get_settings().redis
    if not settings.enabled:
        _available = False
        logger.info(
            "Redis 未启用（QINGCHUAN_AGENT_REDIS_ENABLED=false），checkpoint/事件总线走内存实现"
        )
        return False
    try:
        # 先探测同步（checkpoint 主链路），再探测异步（事件总线）
        get_sync_redis_client().ping()
        await get_async_redis_client().ping()
        _available = True
        logger.info(f"Redis 连接就绪：{settings.connection_url.split('@')[-1]}")
        return True
    except Exception as exc:
        _available = False
        logger.warning(f"Redis 连接失败（{exc}），checkpoint/事件总线降级内存实现，业务不受阻断")
        return False


async def close_redis() -> None:
    """关闭 Redis 连接（lifespan 关闭阶段调用；幂等）。"""
    global _sync_client, _async_client, _available
    try:
        if _async_client is not None:
            await _async_client.aclose()
    except Exception as exc:
        logger.warning(f"关闭 Redis 异步连接异常：{exc}")
    try:
        if _sync_client is not None:
            _sync_client.close()  # redis-py 同步客户端用同步 close（线程安全、幂等）
    except Exception as exc:
        logger.warning(f"关闭 Redis 同步连接异常：{exc}")
    _sync_client = None
    _async_client = None
    _available = False
    logger.info("Redis 连接已关闭")


def _reset_redis_clients() -> None:
    """重置客户端单例与可用性状态（测试隔离用）。"""
    global _sync_client, _async_client, _available
    _sync_client = None
    _async_client = None
    _available = False


__all__ = [
    "close_redis",
    "get_async_redis_client",
    "get_sync_redis_client",
    "init_redis",
    "redis_available",
]
