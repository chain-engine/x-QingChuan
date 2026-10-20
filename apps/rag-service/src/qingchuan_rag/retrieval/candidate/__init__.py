"""
Retrieval/Candidate Package

Stage 2 — 候选召回子包
"""

from qingchuan_rag.retrieval.candidate.base import BaseRetrievalProvider
from qingchuan_rag.retrieval.candidate.keyword_retrieval import (
    BM25Retriever,
    KeywordRetrievalProvider,
)
from qingchuan_rag.retrieval.candidate.vector_retrieval import (
    ChromaVectorRetrieval,
    VectorRetrievalProvider,
)

__all__ = [
    "BaseRetrievalProvider",
    "VectorRetrievalProvider",
    "ChromaVectorRetrieval",
    "KeywordRetrievalProvider",
    "BM25Retriever",
]
