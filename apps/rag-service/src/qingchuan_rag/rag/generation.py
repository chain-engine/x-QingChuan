#!/usr/bin/env python3
"""
Generation Module

生成模块 - 基于 infras.llm 模块的统一 LLM 调用封装
"""

import time as _time
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from qingchuan_rag.core.exceptions import GenerationError
from qingchuan_rag.core.logger import logger
from qingchuan_rag.core.observability import emit
from qingchuan_rag.core.observability.events import FailureEvent, GenerationEvent
from qingchuan_rag.infras.llm import BaseLLMProvider, get_llm_provider


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _extract_usage(response: Any) -> dict | None:
    """从 langchain 响应中提取 token 用量。

    优先取新版 usage_metadata（input_tokens/output_tokens/total_tokens），
    兼容旧版 response_metadata['token_usage']（prompt_tokens/completion_tokens/total_tokens）。
    两者都拿不到时返回 None（模型未返回用量）。
    """
    usage_metadata = getattr(response, "usage_metadata", None) or {}
    if usage_metadata:
        return {
            "prompt_tokens": usage_metadata.get("input_tokens"),
            "completion_tokens": usage_metadata.get("output_tokens"),
            "total_tokens": usage_metadata.get("total_tokens"),
        }
    token_usage = (getattr(response, "response_metadata", None) or {}).get("token_usage") or {}
    if token_usage:
        return {
            "prompt_tokens": token_usage.get("prompt_tokens"),
            "completion_tokens": token_usage.get("completion_tokens"),
            "total_tokens": token_usage.get("total_tokens"),
        }
    return None


class LLMGeneration:
    """LLM生成器 - 基于 infras.llm 的统一调用"""

    def __init__(
        self,
        default_provider: str = "mimo",
        default_model: str = "mimo-v2.6-pro",
        default_temperature: float = 0.7,
        default_max_tokens: int = 2000,
        default_timeout: int = 30,
    ):
        self._default_provider = default_provider
        self._default_model = default_model
        self._default_temperature = default_temperature
        self._default_max_tokens = default_max_tokens
        self._default_timeout = default_timeout
        self._initialized = False
        self._provider: BaseLLMProvider | None = None

    def initialize(self) -> None:
        """初始化"""
        self._provider = get_llm_provider(self._default_provider)
        self._initialized = True
        logger.info(f"LLMGeneration initialized with provider: {self._default_provider}")

    def shutdown(self) -> None:
        """关闭"""
        self._provider = None
        self._initialized = False
        logger.info("LLMGeneration shut down")

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        return {
            "type": "generation",
            "provider": self._default_provider,
            "model": self._default_model,
        }

    async def generate(
        self,
        prompt: str,
        provider: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """生成文本

        Args:
            prompt: 增强后的完整prompt
            provider: LLM提供商（可选，覆盖默认）
            temperature: 温度参数（可选）
            max_tokens: 最大token数（可选）
        """
        self._check_initialized()

        # 确定使用的 provider
        target_provider = provider or self._default_provider
        if target_provider != self._provider.name if self._provider else True:
            self._provider = get_llm_provider(target_provider)

        started_at = _utcnow()
        t0 = _time.perf_counter()
        try:
            # 调用 infras.llm 模块
            # 显式传入 0.0（确定性输出）必须原样传递，不能被 `or` 吞掉回退默认值
            effective_temperature = (
                temperature if temperature is not None else self._default_temperature
            )
            response = self._provider.invoke(
                messages=[{"role": "user", "content": prompt}],
                temperature=effective_temperature,
            )

            # 提取响应内容
            content = response.content if hasattr(response, "content") else str(response)

            # token 用量提取（langchain usage_metadata / token_usage；拿不到则为 None）
            tokens_used = _extract_usage(response)
            latency_ms = (_time.perf_counter() - t0) * 1000
            emit(
                GenerationEvent(
                    tokens=tokens_used,
                    model=self._default_model,
                    latency_ms=latency_ms,
                    started_at=started_at,
                    ended_at=_utcnow(),
                )
            )

            return {
                "text": content,
                "provider": target_provider,
                "model": self._default_model,
                "tokens_used": tokens_used,
            }

        except Exception as e:
            logger.error(f"Generation failed: {e}")
            emit(
                FailureEvent(
                    phase="generation",
                    error_type=type(e).__name__,
                    message=str(e),
                )
            )
            raise GenerationError(f"Generation failed: {e}") from e

    async def stream_generate(
        self,
        prompt: str,
        provider: str | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[str]:
        """流式生成文本

        Args:
            prompt: 提示文本
            provider: LLM提供商
            temperature: 温度参数
        """
        self._check_initialized()

        target_provider = provider or self._default_provider
        if target_provider != self._provider.name if self._provider else True:
            self._provider = get_llm_provider(target_provider)

        try:
            effective_temperature = (
                temperature if temperature is not None else self._default_temperature
            )
            for chunk in self._provider.stream(
                messages=[{"role": "user", "content": prompt}],
                temperature=effective_temperature,
            ):
                if hasattr(chunk, "content"):
                    yield chunk.content
                elif chunk:
                    yield str(chunk)
        except Exception as e:
            logger.error(f"Stream generation failed: {e}")
            raise GenerationError(f"Stream generation failed: {e}") from e

    def _check_initialized(self) -> None:
        """检查是否已初始化"""
        if not self._initialized:
            raise RuntimeError("LLMGeneration not initialized. Call initialize() first.")
