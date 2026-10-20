#!/usr/bin/env python3
"""
Chunking Module

文本切分基础设施：抽象基类 + LangChain / LlamaIndex 两种实现 + 提供者工厂。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from qingchuan_rag.core.logger import logger


@dataclass
class TextChunk:
    """文本分块"""

    content: str
    chunk_id: str
    start_index: int = 0
    end_index: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        return f"TextChunk(id={self.chunk_id}, length={len(self.content)})"


class BaseChunkingProvider(ABC):
    """
    文档切分提供者基类

    所有切分提供者都需要继承此类并实现切分方法。
    """

    name: str = ""
    description: str = ""

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        separators: list[str] | None = None,
        **kwargs,
    ):
        """
        初始化切分提供者

        Args:
            chunk_size: 分块大小（字符数）
            chunk_overlap: 分块重叠大小
            separators: 分隔符列表
            **kwargs: 额外参数
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n\n", "\n", "。", "！", "？", " ", ""]

    @abstractmethod
    def chunk_text(self, text: str, **kwargs) -> list[str]:
        """
        切分文本为字符串列表

        Args:
            text: 待切分的文本
            **kwargs: 额外参数

        Returns:
            切分后的文本块列表
        """
        pass

    def chunk_text_with_metadata(
        self,
        text: str,
        document_id: str = "unknown",
        metadata: dict[str, Any] | None = None,
        **kwargs,
    ) -> list[TextChunk]:
        """
        切分文本并返回带元数据的 TextChunk 列表

        Args:
            text: 待切分的文本
            document_id: 文档ID
            metadata: 额外元数据
            **kwargs: 额外参数

        Returns:
            带有元数据的文本块列表
        """
        chunks = self.chunk_text(text, **kwargs)
        metadata = metadata or {}

        result = []
        for idx, chunk_content in enumerate(chunks):
            chunk_metadata = {
                **metadata,
                "chunk_index": idx,
                "chunk_count": len(chunks),
            }
            result.append(
                TextChunk(
                    content=chunk_content,
                    chunk_id=f"{document_id}_chunk_{idx}",
                    start_index=text.find(chunk_content) if chunk_content in text else 0,
                    end_index=(
                        text.find(chunk_content) + len(chunk_content)
                        if chunk_content in text
                        else len(chunk_content)
                    ),
                    metadata=chunk_metadata,
                )
            )

        return result

    def get_config(self) -> dict[str, Any]:
        """获取当前配置"""
        return {
            "name": self.name,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "separators": self.separators,
        }


class LangchainProvider(BaseChunkingProvider):
    """
    LangChain 文档切分提供者

    支持以下切分器：
    - recursive: RecursiveCharacterTextSplitter（默认）
    - character: CharacterTextSplitter
    - token: TokenTextSplitter
    - semantic: SemanticChunker（需要 embedding 模型）
    """

    name = "langchain"
    description = "LangChain 文档切分提供者（支持 recursive/character/token/semantic）"

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        separators: list[str] | None = None,
        strategy: str = "recursive",
        **kwargs,
    ):
        """
        初始化 LangChain 切分提供者

        Args:
            chunk_size: 分块大小
            chunk_overlap: 分块重叠
            separators: 分隔符列表
            strategy: 切分策略（recursive, character, token, semantic）
            **kwargs: 额外参数
        """
        super().__init__(chunk_size, chunk_overlap, separators, **kwargs)
        self.strategy = strategy
        self._splitter: Any | None = None

    def _get_splitter(self) -> Any:
        """获取或创建切分器实例（懒加载）"""
        if self._splitter is not None:
            return self._splitter

        if self.strategy == "recursive":
            from langchain_text_splitters import RecursiveCharacterTextSplitter

            self._splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                separators=self.separators,
            )
        elif self.strategy == "character":
            from langchain_text_splitters import CharacterTextSplitter

            self._splitter = CharacterTextSplitter(
                separator="\n",
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
            )
        elif self.strategy == "token":
            from langchain_text_splitters import TokenTextSplitter

            self._splitter = TokenTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
            )
        elif self.strategy == "semantic":
            from langchain_community.embeddings import HuggingFaceEmbeddings
            from langchain_text_splitters import SemanticChunker

            embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2",
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )
            self._splitter = SemanticChunker(
                embeddings=embeddings,
                breakpoint_threshold_type="percentile",
            )
        else:
            raise ValueError(f"不支持的切分策略: {self.strategy}")

        logger.info(
            f"创建 LangChain 切分器: strategy={self.strategy}, chunk_size={self.chunk_size}"
        )
        return self._splitter

    def chunk_text(self, text: str, **kwargs) -> list[str]:
        """
        切分文本为字符串列表

        Args:
            text: 待切分的文本
            **kwargs: 额外参数

        Returns:
            切分后的文本块列表
        """
        if not text or not text.strip():
            return []

        splitter = self._get_splitter()
        chunks = splitter.split_text(text)
        logger.debug(f"LangChain 切分完成: {len(chunks)} 个文本块")
        return chunks

    def chunk_documents(self, documents: list, **kwargs) -> list:
        """
        切分 Document 对象列表

        Args:
            documents: LangChain Document 对象列表
            **kwargs: 额外参数

        Returns:
            切分后的 Document 对象列表
        """
        if not documents:
            return []

        splitter = self._get_splitter()

        from langchain.docstore.document import Document as LCDocument

        # 确保输入是 LangChain Document 格式
        lc_documents = []
        for doc in documents:
            if isinstance(doc, LCDocument):
                lc_documents.append(doc)
            elif isinstance(doc, dict):
                lc_documents.append(
                    LCDocument(
                        page_content=doc.get("content", ""), metadata=doc.get("metadata", {})
                    )
                )
            elif isinstance(doc, str):
                lc_documents.append(LCDocument(page_content=doc))
            else:
                lc_documents.append(LCDocument(page_content=str(doc)))

        result = splitter.split_documents(lc_documents)
        logger.debug(f"LangChain Document 切分完成: {len(result)} 个文档块")
        return result

    def get_config(self) -> dict[str, Any]:
        """获取当前配置"""
        return {
            **super().get_config(),
            "strategy": self.strategy,
        }


class LlamaIndexProvider(BaseChunkingProvider):
    """
    LlamaIndex 文档切分提供者

    支持以下切分器：
    - sentence: SentenceSplitter（默认）
    - token: TokenTextSplitter
    - semantic: SemanticSplitterNodeParser（需要 embedding 模型）
    - markdown: MarkdownNodeParser
    """

    name = "llamaindex"
    description = "LlamaIndex 文档切分提供者（支持 sentence/token/semantic/markdown）"

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        separators: list[str] | None = None,
        strategy: str = "sentence",
        **kwargs,
    ):
        """
        初始化 LlamaIndex 切分提供者

        Args:
            chunk_size: 分块大小
            chunk_overlap: 分块重叠
            separators: 分隔符列表
            strategy: 切分策略（sentence, token, semantic, markdown）
            **kwargs: 额外参数
        """
        super().__init__(chunk_size, chunk_overlap, separators, **kwargs)
        self.strategy = strategy
        self._splitter: Any | None = None
        self._extra_kwargs = kwargs

    def _get_splitter(self) -> Any:
        """获取或创建切分器实例（懒加载）"""
        if self._splitter is not None:
            return self._splitter

        if self.strategy == "sentence":
            from llama_index.core.node_parser import SentenceSplitter

            self._splitter = SentenceSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                separator=self.separators[0] if self.separators else "\n\n",
            )
        elif self.strategy == "token":
            from llama_index.core.node_parser import TokenTextSplitter

            self._splitter = TokenTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
            )
        elif self.strategy == "semantic":
            from llama_index.core.embeddings import MockEmbedding
            from llama_index.core.node_parser import SemanticSplitterNodeParser

            # 使用 MockEmbedding 作为默认值，如需真实语义切分请传入自定义 embeddings
            embeddings = self._extra_kwargs.get("embeddings") or MockEmbedding(embed_dim=384)
            self._splitter = SemanticSplitterNodeParser(
                embed_model=embeddings,
                buffer_size=1,
                breakpoint_threshold_type="percentile",
            )
        elif self.strategy == "markdown":
            from llama_index.core.node_parser import MarkdownNodeParser

            self._splitter = MarkdownNodeParser()
        else:
            raise ValueError(f"不支持的切分策略: {self.strategy}")

        logger.info(
            f"创建 LlamaIndex 切分器: strategy={self.strategy}, chunk_size={self.chunk_size}"
        )
        return self._splitter

    def chunk_text(self, text: str, **kwargs) -> list[str]:
        """
        切分文本为字符串列表

        Args:
            text: 待切分的文本
            **kwargs: 额外参数

        Returns:
            切分后的文本块列表
        """
        if not text or not text.strip():
            return []

        from llama_index.core import Document as LIDocument

        splitter = self._get_splitter()
        doc = LIDocument(text=text)
        nodes = splitter.get_nodes_from_documents([doc])
        chunks = [node.get_content() for node in nodes]
        logger.debug(f"LlamaIndex 切分完成: {len(chunks)} 个文本块")
        return chunks

    def chunk_documents(self, documents: list, **kwargs) -> list:
        """
        切分 Document 对象列表

        Args:
            documents: LlamaIndex Document 对象列表
            **kwargs: 额外参数

        Returns:
            切分后的 Node 对象列表
        """
        if not documents:
            return []

        from llama_index.core import Document as LIDocument

        splitter = self._get_splitter()

        # 确保输入是 LlamaIndex Document 格式
        li_documents = []
        for doc in documents:
            if hasattr(doc, "text"):
                li_documents.append(doc)
            elif isinstance(doc, dict):
                li_documents.append(
                    LIDocument(text=doc.get("content", ""), metadata=doc.get("metadata", {}))
                )
            elif isinstance(doc, str):
                li_documents.append(LIDocument(text=doc))
            else:
                li_documents.append(LIDocument(text=str(doc)))

        nodes = splitter.get_nodes_from_documents(li_documents)
        logger.debug(f"LlamaIndex Document 切分完成: {len(nodes)} 个节点")
        return nodes

    def get_config(self) -> dict[str, Any]:
        """获取当前配置"""
        return {
            **super().get_config(),
            "strategy": self.strategy,
        }


_PROVIDERS: dict[str, type[BaseChunkingProvider]] = {
    "langchain": LangchainProvider,
    "llamaindex": LlamaIndexProvider,
}


def get_chunking_provider(provider_name: str = "langchain", **kwargs) -> BaseChunkingProvider:
    """
    获取文档切分提供者实例

    Args:
        provider_name: 提供者名称（langchain, llamaindex）
        **kwargs: 额外的切分参数

    Returns:
        BaseChunkingProvider 实例

    Raises:
        ValueError: 不支持的提供者
    """
    provider_name = provider_name.lower()

    if provider_name not in _PROVIDERS:
        available = ", ".join(_PROVIDERS.keys())
        raise ValueError(f"不支持的切分提供者: {provider_name}。支持的提供者: {available}")

    logger.info(f"Getting document chunking provider: {provider_name}")
    return _PROVIDERS[provider_name](**kwargs)


def list_chunking_providers() -> list[dict[str, str]]:
    """列出所有可用的切分提供者"""
    return [{"name": name, "description": cls.description} for name, cls in _PROVIDERS.items()]


__all__ = [
    "TextChunk",
    "BaseChunkingProvider",
    "LangchainProvider",
    "LlamaIndexProvider",
    "get_chunking_provider",
    "list_chunking_providers",
]
