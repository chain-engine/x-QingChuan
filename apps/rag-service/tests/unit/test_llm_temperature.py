"""LLM provider temperature 覆盖语义测试。

回归：显式传 0.0（确定性输出）不能被 `or` 吞掉回退默认值。
- 显式 0.0 / 0.3 → 必须原样使用；
- 未传 / 显式 None → 回退全局默认 settings.TEMPERATURE。
"""

from __future__ import annotations

import pytest

from qingchuan_rag.core.config import settings
from qingchuan_rag.infras.llm import AliyunProvider, DeepSeekProvider, DoubaoProvider, MimoProvider

PROVIDERS = [DeepSeekProvider, DoubaoProvider, AliyunProvider, MimoProvider]


class TestTemperatureOverride:
    @pytest.mark.parametrize("provider_cls", PROVIDERS)
    def test_explicit_zero_is_preserved(self, provider_cls) -> None:
        """temperature=0.0（确定性输出）必须原样传递，不被 or 吞掉"""
        cfg = provider_cls()._get_config(temperature=0.0)
        assert cfg["temperature"] == 0.0

    @pytest.mark.parametrize("provider_cls", PROVIDERS)
    def test_explicit_value_used(self, provider_cls) -> None:
        cfg = provider_cls()._get_config(temperature=0.3)
        assert cfg["temperature"] == 0.3

    @pytest.mark.parametrize("provider_cls", PROVIDERS)
    def test_missing_falls_back_to_default(self, provider_cls) -> None:
        cfg = provider_cls()._get_config()
        assert cfg["temperature"] == settings.TEMPERATURE

    @pytest.mark.parametrize("provider_cls", PROVIDERS)
    def test_none_falls_back_to_default(self, provider_cls) -> None:
        cfg = provider_cls()._get_config(temperature=None)
        assert cfg["temperature"] == settings.TEMPERATURE
