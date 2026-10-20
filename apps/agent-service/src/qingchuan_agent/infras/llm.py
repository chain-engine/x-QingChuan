#!/usr/bin/env python3
"""大模型调用基础设施（晴川 x-QingChuan，对齐北辰 infras/llm）。

统一 LLM 调用抽象：
    - LangChainLLMProvider：基于 langchain-openai ChatOpenAI（OpenAI 兼容协议）
      —— 可对接 DeepSeek / 豆包方舟 / 本地 vLLM 等，供 Agent 节点编排使用
    - MockLLMProvider：骨架阶段 mock（未配置 API Key 时自动使用，保证可独立启动）

编排层调用方式（LangGraph + LangChain 配合的标准姿势）：
    节点函数内通过 get_llm_provider().get_chat_model() 拿到 LangChain 模型，
    配合 ChatPromptTemplate 构造 prompt，模型返回的 AIMessage 写入图状态。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Any

from qingchuan_agent.core.config import AiLLMSettings, settings
from qingchuan_agent.core.logger import logger


class LLMProvider(ABC):
    """LLM 提供方抽象接口。"""

    @abstractmethod
    def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        """执行一次对话补全，返回文本内容。"""

    @abstractmethod
    def get_chat_model(self) -> Any:
        """返回底层 LangChain ChatModel 实例（供 Agent 节点直接装配 prompt）。"""


class MockLLMProvider(LLMProvider):
    """骨架阶段 Mock 实现：未配置模型时返回固定占位内容，保证编排链路可跑通。"""

    def __init__(self, model_name: str = "mock-llm") -> None:
        self._model_name = model_name

    def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        logger.info(f"[MockLLM] 收到 {len(messages)} 条消息")
        return (
            "【mock 回复】当前为骨架阶段，未配置大模型，"
            "可设置 QINGCHUAN_AGENT_AI_LLM_API_KEY 启用真实模型。"
        )

    def get_chat_model(self) -> Any:
        return None  # 无真实模型，节点需自行处理 None（mock 分支）


class LangChainLLMProvider(LLMProvider):
    """基于 langchain-openai 的 OpenAI 兼容实现。模型实例懒加载。"""

    def __init__(self, config: AiLLMSettings) -> None:
        self._config = config
        self._model: Any | None = None

    def _ensure_model(self) -> Any:
        if self._model is None:
            # 延迟导入：依赖 langchain-openai，未安装时给出明确报错
            from langchain_openai import ChatOpenAI

            self._model = ChatOpenAI(
                base_url=self._config.base_url,
                api_key=self._config.api_key,
                model=self._config.model,
                temperature=self._config.temperature,
                max_tokens=self._config.max_tokens,
                timeout=self._config.timeout_seconds,
            )
        return self._model

    def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        model = self._ensure_model()
        response = model.invoke(messages, **kwargs)
        return str(response.content)

    def get_chat_model(self) -> Any:
        return self._ensure_model()


@lru_cache(maxsize=1)
def get_llm_provider() -> LLMProvider:
    """LLM 提供方工厂（单例）。

    配置了 API Key → 真实 LangChain 实现；否则 → Mock 实现。
    骨架阶段零外部依赖即可启动。
    """
    llm_config: AiLLMSettings = settings.ai.llm
    if settings.ai.enabled and llm_config.api_key:
        provider: LLMProvider = LangChainLLMProvider(llm_config)
        logger.info(f"LLM 初始化：{llm_config.base_url} / {llm_config.model}")
    else:
        provider = MockLLMProvider()
        logger.warning("未配置 QINGCHUAN_AGENT_AI_LLM_API_KEY，LLM 使用 Mock 实现（仅骨架阶段）")
    return provider


__all__ = ["LLMProvider", "LangChainLLMProvider", "MockLLMProvider", "get_llm_provider"]
