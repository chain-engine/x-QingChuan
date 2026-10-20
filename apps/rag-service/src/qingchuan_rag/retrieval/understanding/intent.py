"""
Intent Classification Module

意图识别

— 基于规则识别查询意图类型（事实型、观点型等）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from qingchuan_rag.constants import (
    DEFAULT_INTENT_MIN_CONFIDENCE,
    INTENT_PATTERNS,
    IntentType,
)
from qingchuan_rag.core.logger import logger
from qingchuan_rag.retrieval.understanding.base import (
    BaseQueryUnderstandingProvider,
    QueryUnderstandingResult,
)


@dataclass
class IntentClassification:
    """意图分类结果"""

    primary_intent: IntentType
    confidence: float  # 0.0 - 1.0
    matched_patterns: list[str]  # 匹配到的模式名称


class IntentClassifier(BaseQueryUnderstandingProvider):
    """
    意图识别 — 识别查询类型（事实型、观点型等）

    基于关键词和正则模式匹配识别用户查询的意图类型，
    可作为后续检索策略路由的参考依据。
    """

    name: str = "intent_classifier"
    description: str = "意图识别 — 基于规则识别查询意图类型"

    def __init__(
        self,
        intent_patterns: dict[IntentType, list[tuple[str, float]]] | None = None,
        default_intent: IntentType = IntentType.UNKNOWN,
        min_confidence: float = DEFAULT_INTENT_MIN_CONFIDENCE,
    ):
        """
        初始化意图分类器

        Args:
            intent_patterns: 自定义意图模式（覆盖默认模式）
            default_intent: 未达到最低置信度时的默认意图
            min_confidence: 最低置信度阈值
        """
        self._patterns = intent_patterns or INTENT_PATTERNS
        self._default_intent = default_intent
        self._min_confidence = min_confidence

        self._compiled_patterns: dict[IntentType, list[tuple[re.Pattern, float]]] = {}
        for intent, pattern_list in self._patterns.items():
            self._compiled_patterns[intent] = [
                (re.compile(pattern, re.IGNORECASE), weight) for pattern, weight in pattern_list
            ]

    def supports(self) -> list[str]:
        return ["intent"]

    def _classify(self, query: str) -> IntentClassification:
        """执行意图分类"""
        scores: dict[IntentType, float] = {}
        matched: dict[IntentType, list[str]] = {}

        for intent, compiled in self._compiled_patterns.items():
            scores[intent] = 0.0
            matched[intent] = []
            for pattern, weight in compiled:
                if pattern.search(query):
                    scores[intent] += weight
                    matched[intent].append(pattern.pattern)

        total = sum(scores.values())
        if total > 0:
            for intent in scores:
                scores[intent] /= total

        best_intent = max(scores, key=scores.get)
        confidence = scores[best_intent]

        if confidence < self._min_confidence:
            best_intent = self._default_intent
            confidence = 0.0

        return IntentClassification(
            primary_intent=best_intent,
            confidence=confidence,
            matched_patterns=matched[best_intent],
        )

    def process(
        self,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> QueryUnderstandingResult:
        classification = self._classify(query)

        logger.debug(
            f"IntentClassifier: '{query}' -> {classification.primary_intent.value} "
            f"(conf={classification.confidence:.2f})"
        )

        return QueryUnderstandingResult(
            original_query=query,
            processed_query=query,
            intent=classification.primary_intent.value,
            metadata={
                "provider": self.name,
                "intent_meta": {
                    "intent": classification.primary_intent.value,
                    "confidence": classification.confidence,
                    "matched_patterns": classification.matched_patterns,
                },
            },
        )
