"""
Semantic Reranking Module

语义重排序

— 基于 LLM 语义评分进行重排序
"""

from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from qingchuan_rag.core.logger import logger
from qingchuan_rag.infras.llm import BaseLLMProvider, get_llm_provider
from qingchuan_rag.retrieval.ranking.base import BaseRerankingProvider


class SemanticReranker(BaseRerankingProvider):
    """
    语义重排序器

    使用 LLM 对候选文档与查询的相关性进行语义评分，并据此重新排序。
    """

    name: str = "semantic_reranker"
    description: str = "语义重排序 — 使用 LLM 语义评分重排"

    DEFAULT_SYSTEM_PROMPT: str = """你是一个专业的相关性评分专家。请评估以下文档与查询的相关程度。

评分标准：
1. 完全相关（1.0）：文档内容直接回答了查询
2. 高度相关（0.8）：文档内容大部分与查询相关
3. 中度相关（0.6）：文档部分内容与查询相关
4. 低度相关（0.4）：文档仅有少量内容与查询相关
5. 不相关（0.2）：文档内容与查询无关

要求：
请严格按照上述标准评分，返回0到1之间的小数分数，保留两位小数。"""

    def __init__(
        self,
        llm_provider: BaseLLMProvider | None = None,
        provider_name: str = "mimo",
        system_prompt: str | None = None,
    ) -> None:
        """
        初始化语义重排序器

        Args:
            llm_provider: LLM 提供者实例
            provider_name: LLM 提供者名称
            system_prompt: 评分系统提示词
        """
        self._llm_provider: BaseLLMProvider | None = llm_provider
        self._provider_name: str = provider_name
        self._system_prompt: str = system_prompt or self.DEFAULT_SYSTEM_PROMPT

    def rerank(
        self,
        query: str | list[float],
        candidates: list[dict[str, Any]],
        top_k: int | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """
        使用 LLM 语义评分重排序

        Args:
            query: 查询文本
            candidates: 候选文档列表
            top_k: 返回结果数量
            **kwargs: 额外参数

        Returns:
            list[dict[str, Any]]: 语义重排后的文档列表
        """
        if not candidates:
            return []

        if len(candidates) == 1:
            return candidates[:top_k] if top_k else candidates

        if self._llm_provider is None:
            self._llm_provider = get_llm_provider(self._provider_name)

        scored_docs: list[tuple[float, dict[str, Any]]] = []
        for doc in candidates:
            score = self._score_document(query, doc)
            doc_with_score: dict[str, Any] = {**doc, "semantic_score": score}
            scored_docs.append((score, doc_with_score))

        scored_docs.sort(key=lambda x: x[0], reverse=True)
        result = [doc for _, doc in scored_docs]

        logger.debug(f"SemanticReranker: reranked {len(candidates)} candidates")
        return result[:top_k] if top_k else result

    def _score_document(self, query: str, doc: dict[str, Any]) -> float:
        """使用 LLM 评估文档与查询的相关性"""
        doc_text = doc.get("text", "")[:500]

        scoring_prompt = f"""查询：{query}

文档：{doc_text}

请返回相关性分数（0-1之间的小数）："""

        messages: list[Any] = [
            SystemMessage(content=self._system_prompt),
            HumanMessage(content=scoring_prompt),
        ]

        try:
            response = self._llm_provider.invoke(messages)
            content = response.content if hasattr(response, "content") else str(response)

            match = re.search(r"0?\.\d+", content)
            if match:
                score = float(match.group())
                return min(1.0, max(0.0, score))
        except Exception as e:
            logger.warning(f"SemanticReranker scoring failed: {e}")

        return 0.5
