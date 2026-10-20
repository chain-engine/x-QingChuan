"""
LLM Provider Module

LLM 提供者基础设施：抽象基类 + 多提供商实现。
- DeepSeek
- 豆包 (Doubao)
- 阿里云百炼 (Alibaba Cloud)
- 小米 Mimo
- Mock（测试用）
"""

from __future__ import annotations

from abc import ABC
from typing import Any, ClassVar

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from qingchuan_rag.constants import LLMProviderType
from qingchuan_rag.core.config import Settings
from qingchuan_rag.core.logger import logger


class BaseLLMProvider(ABC):
    """
    LLM 提供者基类

    所有 LLM 提供者都需要继承此类并实现 _get_config 方法。
    """

    provider_type: ClassVar[LLMProviderType]
    name: ClassVar[str]
    description: ClassVar[str]

    def __init__(self) -> None:
        self._chat_model: BaseChatModel | None = None
        self._config_snapshot: dict[str, Any] | None = None

    @staticmethod
    def _get_settings() -> Settings:
        """延迟加载 settings 以避免循环导入"""
        from qingchuan_rag.core.config import settings

        return settings

    def _get_config(self, **overrides: Any) -> dict[str, Any]:
        """
        获取配置（子类必须实现）

        Args:
            **overrides: 运行时覆盖参数

        Returns:
            配置字典
        """
        raise NotImplementedError

    def create_chat_model(self, **kwargs: Any) -> BaseChatModel:
        """
        创建聊天模型实例

        子类可以重写此方法以自定义模型创建逻辑。
        默认实现使用通用的 OpenAI 兼容接口。

        Args:
            **kwargs: 额外的模型参数，会覆盖配置中的默认值

        Returns:
            BaseChatModel 实例
        """
        config = self._get_config(**kwargs)
        logger.info(f"[{self.name}] 创建聊天模型: {config.get('model_name')}")

        return ChatOpenAI(
            api_key=config.get("api_key", ""),
            base_url=config.get("api_base", ""),
            model=config.get("model_name", ""),
            temperature=kwargs.get("temperature", config.get("temperature", 0.0)),
            max_tokens=kwargs.get("max_tokens", config.get("max_tokens")),
            timeout=kwargs.get("timeout", config.get("timeout", 60)),
        )

    def _get_snapshot_key(self, **kwargs: Any) -> dict[str, Any]:
        """获取配置快照的 key，用于检测是否需要重建模型"""
        config = self._get_config(**kwargs)
        return {
            "api_key": config.get("api_key"),
            "api_base": config.get("api_base"),
            "model_name": config.get("model_name"),
        }

    @property
    def chat_model(self) -> BaseChatModel:
        """获取聊天模型（懒加载，检测配置变化自动重建）"""
        current_key = self._get_snapshot_key()

        if self._chat_model is None or self._config_snapshot != current_key:
            self._chat_model = self.create_chat_model()
            self._config_snapshot = current_key

        return self._chat_model

    def invoke(self, messages: list[Any], **kwargs: Any) -> Any:
        """
        调用聊天模型

        Args:
            messages: 消息列表
            **kwargs: 额外参数

        Returns:
            模型响应
        """
        logger.info(f"[{self.name}] 调用 LLM: {len(messages)} 条消息")
        return self.chat_model.invoke(messages, **kwargs)

    def stream(self, messages: list[Any], **kwargs: Any):
        """
        流式调用聊天模型

        Args:
            messages: 消息列表
            **kwargs: 额外参数

        Yields:
            流式响应块
        """
        logger.info(f"[{self.name}] 流式调用 LLM: {len(messages)} 条消息")
        yield from self.chat_model.stream(messages, **kwargs)

    def bind_tools(self, tools: list[Any], **kwargs: Any) -> BaseChatModel:
        """
        绑定工具到聊天模型

        Args:
            tools: 工具列表
            **kwargs: 额外参数

        Returns:
            绑定工具后的聊天模型
        """
        logger.info(f"[{self.name}] 绑定 {len(tools)} 个工具")
        return self.chat_model.bind_tools(tools, **kwargs)

    def with_structured_output(self, schema: Any, **kwargs: Any) -> Any:
        """
        配置结构化输出

        Args:
            schema: 输出模式（Pydantic 模型或 JSON Schema）
            **kwargs: 额外参数

        Returns:
            配置结构化输出的可运行对象
        """
        logger.info(f"[{self.name}] 配置结构化输出")
        return self.chat_model.with_structured_output(schema, **kwargs)


class DeepSeekProvider(BaseLLMProvider):
    """
    DeepSeek LLM 提供者

    支持的模型：
    - deepseek-chat
    - deepseek-reasoner
    """

    provider_type = LLMProviderType.DEEPSEEK
    name = "deepseek"
    description = "DeepSeek 模型提供者"

    def _get_config(self, **overrides: Any) -> dict[str, Any]:
        """获取 DeepSeek 配置"""
        settings = self._get_settings()
        return {
            "api_key": overrides.get("api_key") or settings.DEEPSEEK_API_KEY,
            "api_base": overrides.get("api_base") or settings.DEEPSEEK_API_BASE,
            "model_name": overrides.get("model_name") or settings.DEEPSEEK_MODEL_NAME,
            "temperature": overrides.get("temperature") or settings.TEMPERATURE,
            "max_tokens": overrides.get("max_tokens") or settings.LLM_MAX_TOKENS,
            "timeout": overrides.get("timeout") or settings.LLM_TIMEOUT,
        }


class DoubaoProvider(BaseLLMProvider):
    """
    豆包 (Doubao) LLM 提供者

    支持的模型：
    - doubao-pro-32k
    - doubao-pro-128k
    - doubao-lite-32k
    """

    provider_type = LLMProviderType.DOUBAO
    name = "doubao"
    description = "豆包模型提供者（字节跳动）"

    def _get_config(self, **overrides: Any) -> dict[str, Any]:
        """获取豆包配置"""
        settings = self._get_settings()
        return {
            "api_key": overrides.get("api_key") or settings.DOUBAO_API_KEY,
            "api_base": overrides.get("api_base") or settings.DOUBAO_API_BASE,
            "model_name": overrides.get("model_name") or settings.DOUBAO_MODEL_NAME,
            "temperature": overrides.get("temperature") or settings.TEMPERATURE,
            "max_tokens": overrides.get("max_tokens") or settings.LLM_MAX_TOKENS,
            "timeout": overrides.get("timeout") or settings.LLM_TIMEOUT,
        }


class AliyunProvider(BaseLLMProvider):
    """
    阿里云百炼 (Alibaba Cloud) LLM 提供者

    支持的模型：
    - qwen-turbo
    - qwen-plus
    - qwen-max
    - qwen-max-longcontext
    """

    provider_type = LLMProviderType.ALIYUN
    name = "aliyun"
    description = "阿里云百炼模型提供者（通义千问）"

    def _get_config(self, **overrides: Any) -> dict[str, Any]:
        """获取阿里云配置"""
        settings = self._get_settings()
        return {
            "api_key": overrides.get("api_key") or settings.ALIYUN_API_KEY,
            "api_base": overrides.get("api_base") or settings.ALIYUN_API_BASE,
            "model_name": overrides.get("model_name") or settings.ALIYUN_MODEL_NAME,
            "temperature": overrides.get("temperature") or settings.TEMPERATURE,
            "max_tokens": overrides.get("max_tokens") or settings.LLM_MAX_TOKENS,
            "timeout": overrides.get("timeout") or settings.LLM_TIMEOUT,
        }


class MimoProvider(BaseLLMProvider):
    """
    小米 Mimo LLM 提供者

    支持的模型：
    - mimo-v2.6-pro
    """

    provider_type = LLMProviderType.MIMO
    name = "mimo"
    description = "小米 Mimo 模型提供者"

    def _get_config(self, **overrides: Any) -> dict[str, Any]:
        """获取 Mimo 配置"""
        settings = self._get_settings()
        return {
            "api_key": overrides.get("api_key") or settings.MIMO_API_KEY,
            "api_base": overrides.get("api_base") or settings.MIMO_API_BASE,
            "model_name": overrides.get("model_name") or settings.MIMO_MODEL_NAME,
            "temperature": overrides.get("temperature") or settings.TEMPERATURE,
            "max_tokens": overrides.get("max_tokens") or settings.LLM_MAX_TOKENS,
            "timeout": overrides.get("timeout") or settings.LLM_TIMEOUT,
        }


class MockProvider(BaseLLMProvider):
    """
    模拟 LLM 提供者（用于测试）

    不调用真实的 LLM，返回模拟响应
    """

    provider_type = LLMProviderType.MOCK
    name = "mock"
    description = "模拟模型提供者（用于测试）"

    def _get_config(self, **overrides: Any) -> dict[str, Any]:
        """获取模拟配置"""
        return {
            "api_key": "mock-api-key",
            "api_base": "https://mock.api.com/v1",
            "model_name": "mock-model",
            "temperature": 0.0,
            "max_tokens": None,
            "timeout": 60,
        }

    def invoke(self, messages: list[Any], **kwargs: Any) -> Any:
        """返回模拟响应"""
        from langchain_core.messages import AIMessage

        logger.info("[Mock] 返回模拟响应")
        last_message = messages[-1] if messages else {}
        content = (
            last_message.get("content", "") if isinstance(last_message, dict) else str(last_message)
        )

        if "天气" in content:
            response = "抱歉，我是模拟模型，无法查询实时天气。请配置真实的 API Key。"
        elif "计算" in content or "+" in content or "-" in content:
            response = "模拟计算结果：这是一个测试响应。"
        else:
            response = f"模拟响应：收到您的消息 - {content[:50]}..."

        return AIMessage(content=response)


# 提供者注册表
_PROVIDER_REGISTRY: dict[str, type[BaseLLMProvider]] = {
    provider_type.value: provider_class
    for provider_class in [
        DeepSeekProvider,
        DoubaoProvider,
        AliyunProvider,
        MimoProvider,
        MockProvider,
    ]
    for provider_type in [provider_class.provider_type]
}


def get_llm_provider(provider_name: str) -> BaseLLMProvider:
    """
    获取 LLM 提供者实例

    Args:
        provider_name: 提供者名称（deepseek, doubao, aliyun, mimo, mock）

    Returns:
        BaseLLMProvider 实例

    Raises:
        ValueError: 不支持的提供者
    """
    provider_name = provider_name.lower()

    if provider_name not in _PROVIDER_REGISTRY:
        available = ", ".join(_PROVIDER_REGISTRY.keys())
        raise ValueError(f"不支持的 LLM 提供者: {provider_name}。支持的提供者: {available}")

    logger.info(f"Getting LLM provider: {provider_name}")
    return _PROVIDER_REGISTRY[provider_name]()


def create_chat_model(
    provider_name: str = "mimo",
    model_name: str | None = None,
    temperature: float | None = None,
    **kwargs: Any,
) -> BaseChatModel:
    """
    创建聊天模型的便捷函数

    Args:
        provider_name: 提供者名称
        model_name: 模型名称（可选，覆盖默认配置）
        temperature: 温度参数（可选，覆盖默认配置）
        **kwargs: 其他参数

    Returns:
        BaseChatModel 实例
    """
    provider = get_llm_provider(provider_name)
    return provider.create_chat_model(
        model_name=model_name,
        temperature=temperature,
        **kwargs,
    )


def list_providers() -> list[str]:
    """列出所有可用的 LLM 提供者"""
    return list(_PROVIDER_REGISTRY.keys())


__all__ = [
    "BaseLLMProvider",
    "DeepSeekProvider",
    "DoubaoProvider",
    "AliyunProvider",
    "MimoProvider",
    "MockProvider",
    "get_llm_provider",
    "create_chat_model",
    "list_providers",
]
