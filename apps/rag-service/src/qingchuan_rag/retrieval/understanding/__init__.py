"""
Retrieval/Understanding Package

Stage 1 — 查询理解子包
"""

# IntentType / EntityType 已迁移至 constants.understanding
from qingchuan_rag.constants import EntityType, IntentType
from qingchuan_rag.retrieval.understanding.base import (
    BaseQueryUnderstandingProvider,
    QueryUnderstandingResult,
)
from qingchuan_rag.retrieval.understanding.entity import (
    EntityExtractor,
)
from qingchuan_rag.retrieval.understanding.expansion import (
    EmbeddingExpander,
    QueryExpansionProvider,
    SynonymExpander,
)
from qingchuan_rag.retrieval.understanding.intent import (
    IntentClassifier,
)
from qingchuan_rag.retrieval.understanding.preprocess import (
    QueryPreprocessor,
)
from qingchuan_rag.retrieval.understanding.rewrite import (
    LLMQueryRewriter,
    QueryRewriteProvider,
    SimpleQueryRewriter,
)

__all__ = [
    # Base
    "BaseQueryUnderstandingProvider",
    "QueryUnderstandingResult",
    # Rewrite
    "QueryRewriteProvider",
    "LLMQueryRewriter",
    "SimpleQueryRewriter",
    # Expansion
    "QueryExpansionProvider",
    "SynonymExpander",
    "EmbeddingExpander",
    # Preprocess
    "QueryPreprocessor",
    # Intent
    "IntentClassifier",
    "IntentType",  # re-exported from constants
    # Entity
    "EntityExtractor",
    "EntityType",  # re-exported from constants
]
