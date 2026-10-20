"""
Keyword Retrieval Module

关键词检索召回

— 基于 BM25 算法的召回
"""

from abc import abstractmethod
from typing import Any

from qingchuan_rag.core.logger import logger
from qingchuan_rag.retrieval.candidate.base import BaseRetrievalProvider


class KeywordRetrievalProvider(BaseRetrievalProvider):
    """
    关键词检索提供者基类

    基于关键词（词频/倒排索引）的检索方法，如 BM25。
    """

    name = "keyword_retrieval"
    description = "关键词检索 — 基于词频和倒排索引的召回"

    @property
    def vector_store(self) -> Any:
        raise NotImplementedError("子类必须实现 vector_store 属性")

    @property
    def embedding_model(self) -> Any:
        return None

    @abstractmethod
    def index(self, documents: list[dict[str, Any]]) -> None:
        """为文档建立索引"""
        pass

    @abstractmethod
    def search(
        self,
        query: str,
        top_k: int = 10,
        **kwargs,
    ) -> list[dict[str, Any]]:
        pass


class BM25Retriever(KeywordRetrievalProvider):
    """
    BM25 关键词检索器

    基于 Okapi BM25 算法的关键词检索，使用 rank_bm25 库实现。
    """

    name = "bm25_retriever"
    description = "BM25 检索器 — Okapi BM25 关键词检索"

    def __init__(
        self,
        top_k: int = 10,
        k1: float = 1.5,
        b: float = 0.75,
        document_store: list[dict[str, Any]] | None = None,
    ):
        """
        初始化 BM25 检索器

        Args:
            top_k: 默认召回数量
            k1: BM25 参数，控制词频饱和度
            b: BM25 参数，控制文档长度归一化
            document_store: 文档存储（需预先包含 text 字段）
        """
        self._default_top_k = top_k
        self._k1 = k1
        self._b = b
        self._document_store: list[dict[str, Any]] = document_store or []
        self._bm25 = None
        self._tokenized_corpus: list[list[str]] = []

    @property
    def vector_store(self) -> Any:
        return None

    @property
    def embedding_model(self) -> Any:
        return None

    def _tokenize(self, text: str) -> list[str]:
        """简单中文分词（按字符级别，可替换为 jieba）"""
        import re

        tokens = re.findall(r"[\w]+", text.lower())
        return tokens

    def index(self, documents: list[dict[str, Any]]) -> None:
        """
        为文档建立 BM25 索引

        Args:
            documents: 文档列表，每项需包含 text 字段
        """
        try:
            from rank_bm25 import BM25Okapi
        except ImportError as e:
            logger.error("rank_bm25 not installed. Run: pip install rank-bm25")
            raise ImportError(
                "rank_bm25 is required for BM25Retriever. " "Install with: pip install rank-bm25"
            ) from e

        self._document_store = documents
        self._tokenized_corpus = [self._tokenize(doc.get("text", "")) for doc in documents]

        self._bm25 = BM25Okapi(
            self._tokenized_corpus,
            k1=self._k1,
            b=self._b,
        )
        logger.info(f"BM25Retriever: indexed {len(documents)} documents")

    def add_documents(self, documents: list[dict[str, Any]]) -> None:
        """追加文档到索引"""
        if self._bm25 is None:
            self.index(documents)
            return

        new_tokenized = [self._tokenize(doc.get("text", "")) for doc in documents]
        self._document_store.extend(documents)
        self._tokenized_corpus.extend(new_tokenized)

        from rank_bm25 import BM25Okapi

        self._bm25 = BM25Okapi(
            self._tokenized_corpus,
            k1=self._k1,
            b=self._b,
        )
        logger.info(
            f"BM25Retriever: added {len(documents)} documents, total {len(self._document_store)}"
        )

    def search(
        self,
        query: str,
        top_k: int = 10,
        **kwargs,
    ) -> list[dict[str, Any]]:
        """
        执行 BM25 检索

        Args:
            query: 查询文本
            top_k: 返回结果数量
            **kwargs: 额外参数

        Returns:
            list[dict[str, Any]]: BM25 检索结果
        """
        if self._bm25 is None:
            logger.warning("BM25Retriever: index not built, returning empty results")
            return []

        tokenized_query = self._tokenize(query)
        scores = self._bm25.get_scores(tokenized_query)

        indexed = list(enumerate(scores))
        indexed.sort(key=lambda x: x[1], reverse=True)

        results = []
        max_score = indexed[0][1] if indexed else 1.0
        for idx, score in indexed[:top_k]:
            if max_score > 0:
                normalized_score = score / max_score
            else:
                normalized_score = 0.0

            doc = self._document_store[idx]
            results.append(
                {
                    "id": doc.get("id", f"bm25_{idx}"),
                    "text": doc.get("text", ""),
                    "score": float(normalized_score),
                    "metadata": doc.get("metadata", {}),
                    "embedding": None,
                }
            )

        logger.debug(f"BM25Retriever: found {len(results)} results")
        return results
