"""
Entity Extraction Module

实体抽取

— 基于正则和词典抽取查询中的命名实体。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from qingchuan_rag.constants import ENTITY_PATTERNS, EntityType
from qingchuan_rag.core.logger import logger
from qingchuan_rag.retrieval.understanding.base import (
    BaseQueryUnderstandingProvider,
    QueryUnderstandingResult,
)


@dataclass
class ExtractedEntity:
    """抽取的单个实体"""

    text: str
    type: EntityType
    start: int  # 在原始文本中的起始位置
    end: int  # 在原始文本中的结束位置


@dataclass
class EntityExtraction:
    """实体抽取结果"""

    entities: list[ExtractedEntity] = field(default_factory=list)

    def get_by_type(self, entity_type: EntityType) -> list[ExtractedEntity]:
        """按类型过滤实体"""
        return [e for e in self.entities if e.type == entity_type]

    def get_texts(self) -> list[str]:
        """获取所有实体的文本列表"""
        return [e.text for e in self.entities]


class EntityExtractor(BaseQueryUnderstandingProvider):
    """
    实体抽取 — 基于正则和词表抽取查询中的命名实体

    支持正则模式匹配和自定义词典匹配两类抽取方式。
    """

    name: str = "entity_extractor"
    description: str = "实体抽取 — 抽取查询中的命名实体"

    def __init__(
        self,
        entity_patterns: dict[EntityType, list[str]] | None = None,
        custom_entity_dict: dict[EntityType, set[str]] | None = None,
        case_sensitive: bool = False,
    ):
        """
        初始化实体抽取器

        Args:
            entity_patterns: 自定义正则模式
            custom_entity_dict: 自定义实体词典，如 {EntityType.TECH: {"Python", "RAG", "LLM"}}
            case_sensitive: 词典匹配是否大小写敏感
        """
        self._patterns = entity_patterns or ENTITY_PATTERNS
        self._custom_dict = custom_entity_dict or {}
        self._case_sensitive = case_sensitive

        # 预编译正则
        self._compiled_patterns: dict[EntityType, list[re.Pattern]] = {}
        for etype, patterns in self._patterns.items():
            self._compiled_patterns[etype] = [re.compile(p) for p in patterns]

    def supports(self) -> list[str]:
        return ["entity"]

    def _extract(self, query: str) -> EntityExtraction:
        """执行实体抽取"""
        entities: list[ExtractedEntity] = []
        seen: set[tuple[str, EntityType]] = set()

        # 1. 正则模式匹配
        for etype, patterns in self._compiled_patterns.items():
            for pattern in patterns:
                for match in pattern.finditer(query):
                    key = (match.group(), etype)
                    if key not in seen:
                        seen.add(key)
                        entities.append(
                            ExtractedEntity(
                                text=match.group(),
                                type=etype,
                                start=match.start(),
                                end=match.end(),
                            )
                        )

        # 2. 词典匹配
        for etype, words in self._custom_dict.items():
            query_lower = query if self._case_sensitive else query.lower()
            for word in words:
                word_lower = word if self._case_sensitive else word.lower()
                for match in re.finditer(re.escape(word_lower), query_lower):
                    key = (match.group(), etype)
                    if key not in seen:
                        seen.add(key)
                        entities.append(
                            ExtractedEntity(
                                text=word,
                                type=etype,
                                start=match.start(),
                                end=match.end(),
                            )
                        )

        # 按起始位置排序
        entities.sort(key=lambda e: e.start)
        return EntityExtraction(entities=entities)

    def process(
        self,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> QueryUnderstandingResult:
        extraction = self._extract(query)

        # 统计各类型实体数量
        type_counts: dict[str, int] = {}
        for entity in extraction.entities:
            type_counts[entity.type.value] = type_counts.get(entity.type.value, 0) + 1

        logger.debug(
            f"EntityExtractor: '{query}' -> {len(extraction.entities)} entities, "
            f"types={type_counts}"
        )

        return QueryUnderstandingResult(
            original_query=query,
            processed_query=query,
            metadata={
                "provider": self.name,
                "entity_meta": {
                    "entities": [
                        {
                            "text": e.text,
                            "type": e.type.value,
                            "start": e.start,
                            "end": e.end,
                        }
                        for e in extraction.entities
                    ],
                    "entity_types": type_counts,
                },
            },
        )
