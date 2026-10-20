#!/usr/bin/env python3
"""
Generation Module

生成模块 - 基于 infras.llm 模块的统一 LLM 调用封装
"""

from collections.abc import AsyncIterator
from typing import Any

from qingchuan_rag.core.exceptions import GenerationError
from qingchuan_rag.core.logger import logger
from qingchuan_rag.infras.llm import BaseLLMProvider, get_llm_provider


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

        try:
            # 调用 infras.llm 模块
            response = self._provider.invoke(
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature or self._default_temperature,
            )

            # 提取响应内容
            content = response.content if hasattr(response, "content") else str(response)

            return {
                "text": content,
                "provider": target_provider,
                "model": self._default_model,
                "tokens_used": None,
            }

        except Exception as e:
            logger.error(f"Generation failed: {e}")
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
            for chunk in self._provider.stream(
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature or self._default_temperature,
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
