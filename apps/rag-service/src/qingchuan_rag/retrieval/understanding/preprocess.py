"""
Query Preprocess Module

查询预处理

— 归一化、大小写转换、标点处理、去停用词。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from qingchuan_rag.constants import DEFAULT_QUERY_STOPWORDS
from qingchuan_rag.core.logger import logger
from qingchuan_rag.retrieval.understanding.base import (
    BaseQueryUnderstandingProvider,
    QueryUnderstandingResult,
)


@dataclass
class PreprocessMetadata:
    """预处理阶段的元信息"""

    original_length: int = 0
    processed_length: int = 0
    removed_punctuations: int = 0
    removed_stopwords: int = 0
    case_normalized: bool = False


class QueryPreprocessor(BaseQueryUnderstandingProvider):
    """
    查询预处理 — 归一化、去噪、标点处理

    将用户查询标准化为更适合后续处理的形式。
    """

    name: str = "query_preprocessor"
    description: str = "查询预处理 — 归一化、去噪、标点处理"

    def __init__(
        self,
        lowercase: bool = True,
        remove_punctuation: bool = False,
        strip_whitespace: bool = True,
        stopwords: set[str] | None = None,
        custom_normalizations: list[tuple[str, str]] | None = None,
    ):
        """
        初始化预处理器

        Args:
            lowercase: 是否转为小写（对英文生效）
            remove_punctuation: 是否去除标点符号
            strip_whitespace: 是否去除多余空格
            stopwords: 停用词集合，None 时使用 constants.DEFAULT_QUERY_STOPWORDS
            custom_normalizations: 自定义正则替换规则，如 [("\\\\s+", " ")]
        """
        self._lowercase = lowercase
        self._remove_punctuation = remove_punctuation
        self._strip_whitespace = strip_whitespace
        self._stopwords = stopwords if stopwords is not None else DEFAULT_QUERY_STOPWORDS
        self._custom_normalizations = custom_normalizations or []

        self._custom_re_patterns: list[tuple[re.Pattern, str]] = [
            (re.compile(pattern), replacement)
            for pattern, replacement in self._custom_normalizations
        ]

    def supports(self) -> list[str]:
        return ["preprocess"]

    def _preprocess(self, query: str) -> tuple[str, PreprocessMetadata]:
        """执行预处理"""
        processed = query
        meta = PreprocessMetadata()

        # 1. 自定义正则替换
        for pattern, replacement in self._custom_re_patterns:
            before = len(processed)
            processed = pattern.sub(replacement, processed)
            if before != len(processed):
                meta.processed_length += before - len(processed)

        # 2. 去标点
        if self._remove_punctuation:
            before = len(processed)
            processed = re.sub(r"[^\w\s]", " ", processed)
            meta.removed_punctuations = before - len(processed)

        # 3. 大小写归一化（对英文生效）
        if self._lowercase:
            processed = processed.lower()
            meta.case_normalized = True

        # 4. 停用词过滤
        if self._stopwords:
            words = processed.split()
            filtered = [w for w in words if w not in self._stopwords]
            meta.removed_stopwords = len(words) - len(filtered)
            processed = " ".join(filtered)

        # 5. 空白符归一化
        if self._strip_whitespace:
            processed = " ".join(processed.split())

        meta.original_length = len(query)
        meta.processed_length = len(processed)

        return processed, meta

    def process(
        self,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> QueryUnderstandingResult:
        processed, meta = self._preprocess(query)

        logger.debug(
            f"QueryPreprocessor: len {meta.original_length} -> {meta.processed_length}, "
            f"removed_punct={meta.removed_punctuations}, removed_stop={meta.removed_stopwords}"
        )

        return QueryUnderstandingResult(
            original_query=query,
            processed_query=processed,
            metadata={
                "provider": self.name,
                "preprocess_meta": {
                    "original_length": meta.original_length,
                    "processed_length": meta.processed_length,
                    "removed_punctuations": meta.removed_punctuations,
                    "removed_stopwords": meta.removed_stopwords,
                    "case_normalized": meta.case_normalized,
                },
            },
        )
