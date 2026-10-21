#!/usr/bin/env python3
"""
Chunking Module

文本切分基础设施：抽象基类 + LangChain / LlamaIndex 两种实现 + 提供者工厂。
"""

import re
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


class SemanticSplitter:
    """自研语义切分器（对齐 LangChain SemanticChunker 的 percentile 断点算法）。

    背景：新版 langchain-text-splitters（>=1.1）已移除 SemanticChunker，
    langchain_community 也不再承载 HuggingFaceEmbeddings（官方已迁移至
    langchain-huggingface）。为保持 ``semantic`` 策略可用且与项目检索向量
    一致，这里基于项目 EmbeddingModelBase 接口自研实现：

        1. 按句子分隔符把文本切成句段（段落 → 换行 → 中文句读标点）；
        2. 用 embedding 计算句段向量，取相邻句段余弦相似度 → 距离；
        3. 距离高于 percentile 阈值（默认 95，即仅最不相似的 5% 句边界）处
           视为语义断点，分组后组内贪心合并为不超过 chunk_size 的块。

    ``chunk_overlap`` 参数保留兼容性但不直接应用：语义断点处天然保留断点
    两侧语境，字符级重叠对语义切分意义有限（与 LangChain SemanticChunker
    行为一致）。

    embeddings 对象需实现
    ``encode(texts: list[str], normalize: bool = True) -> list[list[float]]``
    （``qingchuan_rag.infras.embedding.EmbeddingModelBase`` 即满足）；
    缺省时懒加载项目默认 BGE-M3 模型（与向量库检索向量同模型，一致性最优）。
    """

    name = "semantic"
    description = "语义切分器（embedding 余弦相似度 + percentile 断点）"

    # 语义切分专用句段分隔符（句段粒度到句子即可，空格/字符级不再参与）
    _SENTENCE_SEPARATORS: list[str] = ["\n\n", "\n", "。", "！", "？", "；"]

    def __init__(
        self,
        embeddings: Any | None = None,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        separators: list[str] | None = None,
        breakpoint_threshold_type: str = "percentile",
        breakpoint_threshold_amount: float | None = None,
        **kwargs: Any,
    ) -> None:
        self._embeddings = embeddings
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        # separators 仅作配置兼容展示，实际句段切分使用 _SENTENCE_SEPARATORS
        self.separators = separators or ["\n\n", "\n", "。", "！", "？", " ", ""]
        self.breakpoint_threshold_type = breakpoint_threshold_type
        # percentile 默认 95：仅最不相似的 5% 句边界断开
        self.breakpoint_threshold_amount = breakpoint_threshold_amount or 95.0
        self._model: Any | None = None

    def _get_embeddings(self) -> Any:
        """获取 embedding 模型（优先注入对象，缺省懒加载项目默认 BGE-M3）。"""
        if self._embeddings is not None:
            return self._embeddings
        if self._model is None:
            from qingchuan_rag.infras.embedding import BGEEmbeddingModel

            self._model = BGEEmbeddingModel()
        return self._model

    def _split_sentences(self, text: str) -> list[str]:
        """按句子分隔符逐级切分到句段级（断点计算需要句段粒度）。

        - 语义切分必须先切到句子级再按断点合并：chunk_size 只决定"合并"上限，
          不参与"是否切句"的判定，否则大 chunk_size 下整段不切、断点无从计算；
        - 使用 ``re.split`` 捕获分隔符，句段保留句读标点，保证切分结果
          是原文的连续子串（chunk 拼接可还原、start/end 可定位）；
        - 仅当某级分隔符实际切出更细的段时才更新结果；无句读边界的文本
          保持整段（超长时由 split_text 硬切兜底）。
        """
        segments: list[str] = [text]
        for sep in self._SENTENCE_SEPARATORS:
            next_segments: list[str] = []
            for seg in segments:
                # 捕获组保留分隔符，文本 + 标点配对成"带标点句段"
                parts = re.split(f"({re.escape(sep)})", seg)
                buf: str = ""
                rebuilt: list[str] = []
                for part in parts:
                    if part == sep:
                        buf += part
                        if buf.strip():
                            rebuilt.append(buf)
                        buf = ""
                    else:
                        buf += part
                if buf.strip():
                    rebuilt.append(buf)
                next_segments.extend(rebuilt)
            # 该分隔符未产生更细的段（长度相同且内容一致）则跳过
            if len(next_segments) == len(segments) and all(
                a == b for a, b in zip(next_segments, segments, strict=False)
            ):
                continue
            segments = [s for s in next_segments if s and s.strip()]
        return [s.strip() for s in segments if s and s.strip()]

    def split_text(self, text: str) -> list[str]:
        """语义切分文本为字符串列表。"""
        if not text or not text.strip():
            return []

        sentences = self._split_sentences(text)
        if len(sentences) <= 1:
            # 无句读边界：整段返回；超长时硬切兜底（避免产出超 chunk_size 的块）
            stripped = text.strip()
            if len(stripped) > self.chunk_size:
                return self._hard_split(stripped)
            return [stripped]

        embeddings = self._get_embeddings()
        vectors = embeddings.encode(sentences, normalize=True)
        if not vectors:
            return [text.strip()]

        import numpy as np

        arr = np.asarray(vectors, dtype=np.float64)
        norms = np.linalg.norm(arr, axis=1)
        # 防御零向量（极端情况置为 1，距离退化为 1 - 0 = 1）
        norms[norms == 0] = 1.0
        arr = arr / norms[:, None]
        dots = (arr[:-1] * arr[1:]).sum(axis=1)  # 相邻句段余弦相似度
        distances = 1.0 - dots

        if self.breakpoint_threshold_type == "percentile":
            threshold = float(np.percentile(distances, self.breakpoint_threshold_amount))
        else:
            # standard_deviation / gradient：简化为均值 + 1σ 断点
            threshold = float(distances.mean() + distances.std())

        breaks: list[int] = [i + 1 for i, d in enumerate(distances) if d > threshold]

        # 按断点分组
        groups: list[list[str]] = []
        current: list[str] = []
        for idx, sentence in enumerate(sentences):
            current.append(sentence)
            if idx + 1 in breaks or idx == len(sentences) - 1:
                groups.append(current)
                current = []

        chunks: list[str] = []
        for group in groups:
            chunks.extend(self._merge_group(group))
        return chunks

    def _merge_group(self, group: list[str]) -> list[str]:
        """组内贪心合并句段为不超过 chunk_size 的块；超长句段独立硬切。"""
        merged: list[str] = []
        buf: str = ""
        for sentence in group:
            if len(sentence) > self.chunk_size:
                if buf:
                    merged.append(buf)
                    buf = ""
                merged.extend(self._hard_split(sentence))
                continue
            if len(buf) + len(sentence) <= self.chunk_size:
                buf += sentence
            else:
                if buf:
                    merged.append(buf)
                buf = sentence
        if buf:
            merged.append(buf)
        return [c for c in merged if c and c.strip()]

    def _hard_split(self, sentence: str) -> list[str]:
        """超长句段按 chunk_size 硬切。"""
        return [sentence[i : i + self.chunk_size] for i in range(0, len(sentence), self.chunk_size)]

    def get_config(self) -> dict[str, Any]:
        """获取当前配置。"""
        return {
            "name": self.name,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "breakpoint_threshold_type": self.breakpoint_threshold_type,
            "breakpoint_threshold_amount": self.breakpoint_threshold_amount,
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
        self._extra_kwargs = kwargs

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
            # 自研语义切分：新版 langchain-text-splitters 已移除 SemanticChunker，
            # 这里用 embedding 余弦相似度 + percentile 断点实现等价语义切分。
            # embeddings 可注入（需实现 encode(texts) -> list[list[float]]），
            # 缺省懒加载项目默认 BGE-M3（与检索向量同模型，一致性最优）。
            self._splitter = SemanticSplitter(
                embeddings=self._extra_kwargs.get("embeddings"),
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                separators=self.separators,
                breakpoint_threshold_type=self._extra_kwargs.get(
                    "breakpoint_threshold_type", "percentile"
                ),
                breakpoint_threshold_amount=self._extra_kwargs.get(
                    "breakpoint_threshold_amount", 95.0
                ),
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
    "SemanticSplitter",
    "LangchainProvider",
    "LlamaIndexProvider",
    "get_chunking_provider",
    "list_chunking_providers",
]
