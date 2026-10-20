"""
Query Rewrite Module

查询重写

— 将用户查询改写为更适合检索的形式
"""

from abc import abstractmethod
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from qingchuan_rag.core.logger import logger
from qingchuan_rag.infras.llm import BaseLLMProvider, get_llm_provider
from qingchuan_rag.retrieval.understanding.base import (
    BaseQueryUnderstandingProvider,
    QueryUnderstandingResult,
)


class QueryRewriteProvider(BaseQueryUnderstandingProvider):
    """
    查询重写提供者基类

    将用户查询改写为更清晰、更适合向量检索的形式。
    """

    name = "query_rewrite"
    description = "查询重写 — 改写用户查询以提升检索效果"

    def supports(self) -> list[str]:
        return ["rewrite"]

    @abstractmethod
    def rewrite(self, query: str) -> str:
        """执行查询重写"""
        pass

    def process(
        self,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> QueryUnderstandingResult:
        """重写查询并返回结果"""
        rewritten = self.rewrite(query)
        return QueryUnderstandingResult(
            original_query=query,
            processed_query=rewritten,
            metadata={"provider": self.name},
        )


class LLMQueryRewriter(QueryRewriteProvider):
    """
    基于 LLM 的查询重写

    使用大语言模型将查询改写为更清晰、更完整的检索形式。
    """

    name = "llm_query_rewriter"
    description = "LLM 查询重写器 — 使用大语言模型改写查询"

    def __init__(
        self,
        llm_provider: BaseLLMProvider | None = None,
        provider_name: str = "mimo",
        system_prompt: str | None = None,
    ):
        """
        初始化 LLM 查询重写器

        Args:
            llm_provider: LLM 提供者实例（可选）
            provider_name: LLM 提供者名称
            system_prompt: 系统提示词
        """
        self._llm_provider = llm_provider
        self._provider_name = provider_name
        self._system_prompt = system_prompt or (
            "你是一个专业的查询改写专家。你的任务是将用户输入的查询改写为更适合向量检索的形式。\n\n"
            "要求：\n"
            "1. 消除歧义，明确表达用户的真实意图\n"
            "2. 补充必要的上下文信息\n"
            "3. 使用更规范、更完整的表述\n"
            "4. 如果查询已经是最佳形式，保持不变\n\n"
            "只返回改写后的查询，不要其他解释。"
        )

    def rewrite(self, query: str) -> str:
        """使用 LLM 重写查询"""
        if self._llm_provider is None:
            self._llm_provider = get_llm_provider(self._provider_name)

        messages = [
            SystemMessage(content=self._system_prompt),
            HumanMessage(content=query),
        ]

        try:
            response = self._llm_provider.invoke(messages)
            rewritten = response.content if hasattr(response, "content") else str(response)
            logger.debug(f"LLMQueryRewriter: '{query}' -> '{rewritten}'")
            return rewritten.strip()
        except Exception as e:
            logger.warning(f"LLMQueryRewriter failed: {e}, falling back to original query")
            return query


class SimpleQueryRewriter(QueryRewriteProvider):
    """
    简单规则查询重写

    使用规则和同义词替换改写查询，适用于快速测试或无 LLM 场景。
    """

    name = "simple_query_rewriter"
    description = "简单规则查询重写 — 基于规则和同义词的快速改写"

    def __init__(
        self,
        synonym_map: dict[str, list[str]] | None = None,
        expansion_patterns: list[tuple[str, str]] | None = None,
    ):
        """
        初始化简单查询重写器

        Args:
            synonym_map: 同义词映射，如 {"GPU": ["显卡", "显示芯片"]}
            expansion_patterns: 扩展模式，如 [("是什么", ""), ("怎么用", "使用方法")]
        """
        self._synonym_map = synonym_map or {}
        self._expansion_patterns = expansion_patterns or [
            ("是什么", ""),
            ("怎么用", "使用方法"),
            ("如何", "怎样"),
            ("请问", ""),
            ("帮我", ""),
        ]

    def rewrite(self, query: str) -> str:
        """基于规则重写查询"""
        rewritten = query

        for pattern, replacement in self._expansion_patterns:
            if pattern in rewritten:
                rewritten = rewritten.replace(pattern, replacement)

        for term, synonyms in self._synonym_map.items():
            if term in rewritten:
                rewritten = rewritten.replace(term, f"{term} {' '.join(synonyms)}")

        rewritten = " ".join(rewritten.split())
        logger.debug(f"SimpleQueryRewriter: '{query}' -> '{rewritten}'")
        return rewritten
