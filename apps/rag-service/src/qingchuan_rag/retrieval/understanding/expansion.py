"""
Query Expansion Module

查询扩展

— 扩展查询以增加召回率
"""

from abc import abstractmethod
from typing import Any

from qingchuan_rag.core.logger import logger
from qingchuan_rag.retrieval.understanding.base import (
    BaseQueryUnderstandingProvider,
    QueryUnderstandingResult,
)


class QueryExpansionProvider(BaseQueryUnderstandingProvider):
    """
    查询扩展提供者基类

    通过扩展查询术语或向量空间邻居来增加检索的召回率。
    """

    name = "query_expansion"
    description = "查询扩展 — 扩展查询术语以提升召回率"

    def supports(self) -> list[str]:
        return ["expansion"]

    @abstractmethod
    def expand(self, query: str) -> tuple[str, list[str]]:
        """
        执行查询扩展

        Args:
            query: 原始查询

        Returns:
            tuple[str, list[str]]: (扩展后的查询, 扩展的术语列表)
        """
        pass

    def process(
        self,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> QueryUnderstandingResult:
        """扩展查询并返回结果"""
        expanded_query, expanded_terms = self.expand(query)
        return QueryUnderstandingResult(
            original_query=query,
            processed_query=expanded_query,
            expanded_terms=expanded_terms,
            metadata={"provider": self.name},
        )


class SynonymExpander(QueryExpansionProvider):
    """
    同义词扩展

    使用预定义的同义词库扩展查询。
    """

    name = "synonym_expander"
    description = "同义词扩展 — 使用同义词库扩展查询术语"

    def __init__(
        self,
        synonym_dict: dict[str, list[str]] | None = None,
        max_expansions: int = 5,
    ):
        """
        初始化同义词扩展器

        Args:
            synonym_dict: 同义词字典，如 {"machine learning": ["ML", "机器学习"]}
            max_expansions: 最大扩展术语数量
        """
        self._synonym_dict = synonym_dict or self._default_synonyms()
        self._max_expansions = max_expansions

    def _default_synonyms(self) -> dict[str, list[str]]:
        """默认同义词库"""
        return {
            "AI": ["人工智能", "Artificial Intelligence"],
            "ML": ["机器学习", "Machine Learning"],
            "NLP": ["自然语言处理", "Natural Language Processing"],
            "LLM": ["大语言模型", "Large Language Model"],
            "RAG": ["检索增强生成", "Retrieval Augmented Generation"],
            "GPU": ["显卡", "显示芯片"],
            "CPU": ["中央处理器"],
            "API": ["应用程序接口"],
            "bug": ["缺陷", "错误"],
            "debug": ["调试", "排错"],
        }

    def expand(self, query: str) -> tuple[str, list[str]]:
        """使用同义词扩展查询"""
        expanded_terms = []
        expanded_query = query

        for term, synonyms in self._synonym_dict.items():
            if term.lower() in query.lower():
                for syn in synonyms[: self._max_expansions]:
                    if syn not in expanded_query:
                        expanded_terms.append(syn)
                        expanded_query += f" {syn}"

        logger.debug(f"SynonymExpander expanded {len(expanded_terms)} terms: {expanded_terms}")
        return expanded_query, expanded_terms


class EmbeddingExpander(QueryExpansionProvider):
    """
    向量空间扩展

    使用 embedding 模型找到与查询语义相似的额外术语进行扩展。
    """

    name = "embedding_expander"
    description = "向量空间扩展 — 基于语义相似度扩展查询"

    def __init__(
        self,
        embedding_model: Any,
        top_k: int = 5,
        vocabulary: list[str] | None = None,
    ):
        """
        初始化向量空间扩展器

        Args:
            embedding_model: embedding 模型（需实现 encode / encode_single）
            top_k: 扩展的最近邻数量
            vocabulary: 候选词汇表
        """
        self._embedding_model = embedding_model
        self._top_k = top_k
        self._vocabulary = vocabulary or []

    def expand(self, query: str) -> tuple[str, list[str]]:
        """基于向量相似度扩展查询"""
        if not self._vocabulary or self._embedding_model is None:
            return query, []

        try:
            query_embedding = self._embedding_model.encode_single(query)
            vocab_embeddings = self._embedding_model.encode(self._vocabulary)

            from qingchuan_rag.utils.similarity import DistanceType, SimilaritySearchEngine

            engine = SimilaritySearchEngine(distance_type=DistanceType.COSINE)
            similarities = engine.compute_batch(query_embedding, vocab_embeddings)

            indexed = list(zip(similarities, self._vocabulary, strict=False))
            indexed.sort(reverse=True)

            top_terms = [term for _, term in indexed[: self._top_k]]
            expanded_query = f"{query} {' '.join(top_terms)}"

            logger.debug(f"EmbeddingExpander expanded with: {top_terms}")
            return expanded_query, top_terms
        except Exception as e:
            logger.warning(f"EmbeddingExpander failed: {e}")
            return query, []
