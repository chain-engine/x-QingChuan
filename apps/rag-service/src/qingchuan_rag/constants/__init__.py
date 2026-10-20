#!/usr/bin/env python3
"""
Constants Package

统一管理项目中的常量，避免魔法数值和硬编码字符串。
枚举定义统一收敛于 enums.py，常量定义统一收敛于 constants.py，
枚举基类族保留在 base.py。
"""

from qingchuan_rag.constants.base import BaseEnum
from qingchuan_rag.constants.constants import (
    API_PREFIX,
    APP_DESCRIPTION,
    APP_ID,
    APP_NAME,
    APP_VERSION,
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_CONFIG_FILE,
    DEFAULT_EMBEDDING_BATCH_SIZE,
    DEFAULT_EMBEDDING_CACHE_SIZE,
    DEFAULT_EMBEDDING_DEVICE,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_INTENT_MIN_CONFIDENCE,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MMR_LAMBDA,
    DEFAULT_QUERY_STOPWORDS,
    DEFAULT_SIMILARITY_THRESHOLD,
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_TEMPERATURE,
    DEFAULT_TIMEOUT,
    DEFAULT_TOP_K,
    DEFAULT_USER_PROMPT_TEMPLATE,
    DISTANCE_COSINE,
    DISTANCE_DOT,
    DISTANCE_EUCLIDEAN,
    ENTITY_PATTERNS,
    INTENT_PATTERNS,
    SUPPORTED_DOC_TYPES,
)
from qingchuan_rag.constants.enums import (
    DistanceType,
    DocStatus,
    DocType,
    EntityType,
    HeaderType,
    HttpStatus,
    IntentType,
    LLMProviderType,
    RerankingProviderName,
)

__all__ = [
    # BaseEnum
    "BaseEnum",
    # HTTP Status
    "HttpStatus",
    # Headers
    "HeaderType",
    # Document Status
    "DocStatus",
    # Document Types
    "DocType",
    "SUPPORTED_DOC_TYPES",
    # Distance Types
    "DISTANCE_COSINE",
    "DISTANCE_EUCLIDEAN",
    "DISTANCE_DOT",
    "DistanceType",
    # RAG Defaults
    "DEFAULT_TOP_K",
    "DEFAULT_SIMILARITY_THRESHOLD",
    "DEFAULT_MMR_LAMBDA",
    "DEFAULT_CHUNK_SIZE",
    "DEFAULT_CHUNK_OVERLAP",
    # Prompt Templates
    "DEFAULT_SYSTEM_PROMPT",
    "DEFAULT_USER_PROMPT_TEMPLATE",
    # RAG Enums
    "RerankingProviderName",
    # LLM Providers
    "LLMProviderType",
    # Embedding
    "DEFAULT_EMBEDDING_MODEL",
    "DEFAULT_EMBEDDING_DEVICE",
    "DEFAULT_EMBEDDING_BATCH_SIZE",
    "DEFAULT_EMBEDDING_CACHE_SIZE",
    # Generation
    "DEFAULT_TEMPERATURE",
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_TIMEOUT",
    # Server
    "API_PREFIX",
    "APP_ID",
    "APP_NAME",
    "APP_DESCRIPTION",
    "APP_VERSION",
    "DEFAULT_CONFIG_FILE",
    # Understanding
    "IntentType",
    "EntityType",
    "INTENT_PATTERNS",
    "ENTITY_PATTERNS",
    "DEFAULT_INTENT_MIN_CONFIDENCE",
    "DEFAULT_QUERY_STOPWORDS",
]
