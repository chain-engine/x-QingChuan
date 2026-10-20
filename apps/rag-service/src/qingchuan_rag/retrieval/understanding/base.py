"""
Query Understanding Base Module

Stage 1 — 查询理解抽象基类
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class QueryUnderstandingResult:
    """查询理解结果"""

    original_query: str
    processed_query: str
    intent: str | None = None
    sub_queries: list[str] = field(default_factory=list)
    hypothetical_doc: str | None = None
    expanded_terms: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        return (
            f"QueryUnderstandingResult(original={self.original_query!r}, "
            f"processed={self.processed_query!r}, "
            f"sub_queries={len(self.sub_queries)})"
        )

    def merge(self, other: "QueryUnderstandingResult") -> "QueryUnderstandingResult":
        """
        合并另一个理解结果（用于并行执行后的结果聚合）

        - processed_query: 取最长（信息量最丰富）的查询
        - sub_queries: 合并去重
        - expanded_terms: 合并去重
        - hypothetical_doc: 合并所有假设文档
        - metadata: 合并两个 metadata dict

        Args:
            other: 待合并的结果

        Returns:
            QueryUnderstandingResult: 合并后的结果
        """
        merged_sub_queries = list(dict.fromkeys(self.sub_queries + other.sub_queries))
        merged_terms = list(dict.fromkeys(self.expanded_terms + other.expanded_terms))

        hyde_docs = []
        if self.hypothetical_doc:
            hyde_docs.append(self.hypothetical_doc)
        if other.hypothetical_doc:
            hyde_docs.append(other.hypothetical_doc)

        processed = self.processed_query
        if len(other.processed_query) > len(processed):
            processed = other.processed_query

        merged_metadata = {**self.metadata, **other.metadata}
        if self.original_query == other.original_query:
            merged_metadata["original_query"] = self.original_query
        merged_metadata.setdefault("providers", []).extend(
            [self.metadata.get("provider"), other.metadata.get("provider")]
        )

        return QueryUnderstandingResult(
            original_query=self.original_query,
            processed_query=processed,
            intent=self.intent or other.intent,
            sub_queries=merged_sub_queries,
            hypothetical_doc="\n".join(hyde_docs) if hyde_docs else None,
            expanded_terms=merged_terms,
            metadata=merged_metadata,
        )


class BaseQueryUnderstandingProvider(ABC):
    """
    查询理解提供者基类

    所有查询理解子能力的提供者都需要继承此类并实现 process 方法。
    查询理解包括：Query Rewrite、Query Expansion、HyDE、Subquery Decomposition。
    """

    name: str = ""
    description: str = ""

    @abstractmethod
    def process(
        self,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> QueryUnderstandingResult:
        """
        对查询进行处理

        Args:
            query: 原始查询文本
            context: 上下文信息（如对话历史）

        Returns:
            QueryUnderstandingResult: 处理后的结果
        """
        pass

    @abstractmethod
    def supports(self) -> list[str]:
        """
        返回该提供者支持的子能力名称列表

        Returns:
            list[str]: 支持的能力名，如 ["rewrite"]、["hyde"] 等
        """
        pass

    def get_config(self) -> dict[str, Any]:
        """获取当前配置"""
        return {
            "name": self.name,
            "description": self.description,
        }
