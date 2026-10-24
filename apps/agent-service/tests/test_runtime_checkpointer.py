"""AgentRuntime checkpointer 测试：memory 默认 / redis 可用与降级。"""

import asyncio

import pytest
from qingchuan_agent.agents.runtime import AgentRuntime
from qingchuan_agent.core.config import get_settings


def test_checkpointer_default_memory():
    """默认配置（memory）返回 MemorySaver。"""
    from langgraph.checkpoint.memory import MemorySaver

    runtime = AgentRuntime()
    checkpointer = runtime._get_checkpointer()
    assert isinstance(checkpointer, MemorySaver)
    assert runtime._get_checkpointer() is checkpointer  # 缓存复用


def test_checkpointer_redis_unavailable_falls_back():
    """checkpoint=redis 但 Redis 未启用 → 运行期回退 MemorySaver（不阻断）。"""
    from langgraph.checkpoint.memory import MemorySaver

    settings = get_settings()
    original_checkpoint = settings.agent.checkpoint
    original_enabled = settings.redis.enabled
    settings.agent.checkpoint = "redis"
    settings.redis.enabled = False
    try:
        runtime = AgentRuntime()
        checkpointer = runtime._get_checkpointer()
        assert isinstance(checkpointer, MemorySaver)
    finally:
        settings.agent.checkpoint = original_checkpoint
        settings.redis.enabled = original_enabled


def test_checkpointer_redis_real(monkeypatch):
    """checkpoint=redis + Redis 可用 → RedisSaver（本地 Redis 不可用时跳过）。"""
    from qingchuan_agent.infras.redis import (
        _reset_redis_clients,
        close_redis,
        init_redis,
    )

    settings = get_settings()
    original_checkpoint = settings.agent.checkpoint
    original_enabled = settings.redis.enabled
    original_db = settings.redis.db
    settings.agent.checkpoint = "redis"
    settings.redis.enabled = True
    settings.redis.db = 15  # 隔离测试库，避免污染生产 db
    try:
        available = asyncio.run(init_redis())
        if not available:
            pytest.skip("本地 Redis 不可用，跳过 RedisSaver 集成测试")
        from qingchuan_agent.infras.redis import get_sync_redis_client

        # RedisSaver 依赖 RediSearch 模块（FT.* 命令）；无该模块时 runtime 按设计
        # 降级 MemorySaver，断言无意义，跳过（本机 Docker Redis / CI 官方镜像均无）。
        try:
            modules = get_sync_redis_client().execute_command("MODULE LIST")
        except Exception:
            modules = []
        if not any(b"search" in (m[0] if isinstance(m, (list, tuple)) else b"") for m in modules):
            pytest.skip("Redis 缺少 RediSearch 模块，跳过 RedisSaver 集成测试")
        from langgraph.checkpoint.redis import RedisSaver

        runtime = AgentRuntime()
        checkpointer = runtime._get_checkpointer()
        assert isinstance(checkpointer, RedisSaver)
    finally:
        asyncio.run(close_redis())
        _reset_redis_clients()
        settings.agent.checkpoint = original_checkpoint
        settings.redis.enabled = original_enabled
        settings.redis.db = original_db
