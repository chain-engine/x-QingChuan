"""LLMGeneration 层 temperature 覆盖语义测试。

回归：显式传 0.0（确定性输出）不能被 `or` 吞掉回退默认值。
与 test_llm_temperature.py（infras 层）互补，本文件覆盖 rag/generation.py 层：
- generate / stream_generate 显式 0.0 / 0.3 → 必须原样传给 provider；
- 未传 / 显式 None → 回退构造时 default_temperature。
使用假 provider 记录实际透传值，不发起真实 LLM 网络调用。
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from qingchuan_rag.rag.generation import LLMGeneration


class _FakeProvider:
    """记录 invoke/stream 参数的假 provider，name 固定为默认 provider 避免重建。"""

    name = "mimo"

    def __init__(self) -> None:
        self.invoke_kwargs: dict = {}
        self.stream_kwargs: dict = {}

    def invoke(self, messages: list, **kwargs):
        self.invoke_kwargs = {"messages": messages, **kwargs}
        return SimpleNamespace(content="ok")

    def stream(self, messages: list, **kwargs):
        self.stream_kwargs = {"messages": messages, **kwargs}
        yield SimpleNamespace(content="ok")


def _make_generation(default_temperature: float = 0.7) -> tuple[LLMGeneration, _FakeProvider]:
    gen = LLMGeneration(default_temperature=default_temperature)
    gen.initialize()
    fake = _FakeProvider()
    gen._provider = fake  # type: ignore[assignment]  # 测试桩替换，避免真实网络调用
    return gen, fake


class TestGenerationTemperature:
    def test_explicit_zero_is_preserved(self) -> None:
        gen, fake = _make_generation()
        asyncio.run(gen.generate(prompt="p", temperature=0.0))
        assert fake.invoke_kwargs["temperature"] == 0.0

    def test_explicit_value_used(self) -> None:
        gen, fake = _make_generation()
        asyncio.run(gen.generate(prompt="p", temperature=0.3))
        assert fake.invoke_kwargs["temperature"] == 0.3

    def test_missing_falls_back_to_default(self) -> None:
        gen, fake = _make_generation(default_temperature=0.5)
        asyncio.run(gen.generate(prompt="p"))
        assert fake.invoke_kwargs["temperature"] == 0.5

    def test_none_falls_back_to_default(self) -> None:
        gen, fake = _make_generation(default_temperature=0.5)
        asyncio.run(gen.generate(prompt="p", temperature=None))
        assert fake.invoke_kwargs["temperature"] == 0.5

    def test_stream_explicit_zero_is_preserved(self) -> None:
        gen, fake = _make_generation()

        async def consume() -> None:
            chunks = [c async for c in gen.stream_generate(prompt="p", temperature=0.0)]
            assert chunks == ["ok"]

        asyncio.run(consume())
        assert fake.stream_kwargs["temperature"] == 0.0

    def test_stream_none_falls_back_to_default(self) -> None:
        gen, fake = _make_generation(default_temperature=0.4)

        async def consume() -> None:
            _ = [c async for c in gen.stream_generate(prompt="p", temperature=None)]

        asyncio.run(consume())
        assert fake.stream_kwargs["temperature"] == 0.4
