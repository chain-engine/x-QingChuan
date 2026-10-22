#!/usr/bin/env python3
"""
Infras Package

基础设施层，封装第三方中间件、客户端、连接生命周期。
模块文件平铺：storage.py（文档存储）、embedding.py（嵌入模型）、
vector.py（向量存储抽象基类 + Chroma 实现）、bm25.py（BM25 稀疏索引）、
llm.py（LLM 提供者抽象基类 + 多提供商实现）、
chunking.py（文本切分抽象基类 + LangChain / LlamaIndex 实现）。
"""

from qingchuan_rag.infras.bm25 import BM25IndexStore
from qingchuan_rag.infras.chunking import (
    BaseChunkingProvider,
    LangchainProvider,
    LlamaIndexProvider,
    TextChunk,
    get_chunking_provider,
    list_chunking_providers,
)
from qingchuan_rag.infras.embedding import BGEEmbeddingModel, EmbeddingModelBase
from qingchuan_rag.infras.hrss import SOURCE_HRSS, HRSSDataSourceClient
from qingchuan_rag.infras.llm import (
    AliyunProvider,
    BaseLLMProvider,
    DeepSeekProvider,
    DoubaoProvider,
    MimoProvider,
    MockProvider,
    create_chat_model,
    get_llm_provider,
    list_providers,
)
from qingchuan_rag.infras.storage import (
    LocalStorage,
    S3CompatibleStorage,
    StorageProvider,
    UploadResult,
    get_cached_storage_provider,
    get_storage_provider,
)
from qingchuan_rag.infras.vector import ChromaVectorStore, VectorStoreBase

__all__ = [
    "StorageProvider",
    "LocalStorage",
    "S3CompatibleStorage",
    "UploadResult",
    "get_storage_provider",
    "get_cached_storage_provider",
    "EmbeddingModelBase",
    "BGEEmbeddingModel",
    "VectorStoreBase",
    "ChromaVectorStore",
    "BM25IndexStore",
    "HRSSDataSourceClient",
    "SOURCE_HRSS",
    "TextChunk",
    "BaseChunkingProvider",
    "LangchainProvider",
    "LlamaIndexProvider",
    "get_chunking_provider",
    "list_chunking_providers",
    "BaseLLMProvider",
    "DeepSeekProvider",
    "DoubaoProvider",
    "AliyunProvider",
    "MimoProvider",
    "MockProvider",
    "get_llm_provider",
    "create_chat_model",
    "list_providers",
]
