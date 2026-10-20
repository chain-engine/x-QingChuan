#!/usr/bin/env python3
"""
BM25 Sparse Index Module

基于 rank_bm25 的稀疏索引（倒排索引）实现
用于关键词召回，与稠密向量索引互补实现多路召回
"""

import json
import os
from typing import Any

from qingchuan_rag.core.exceptions import VectorStoreError
from qingchuan_rag.core.logger import logger


class BM25IndexStore:
    """
    BM25 稀疏索引存储

    使用 rank_bm25 库实现 BM25 算法，构建倒排索引。
    适用于关键词精确匹配和词项召回。
    """

    def __init__(
        self,
        persist_directory: str = "./data/bm25",
        index_name: str = "default",
        k1: float = 1.5,
        b: float = 0.75,
    ):
        """
        初始化 BM25 索引存储

        Args:
            persist_directory: 持久化存储目录
            index_name: 索引名称
            k1: BM25 参数，控制词频饱和度
            b: BM25 参数，控制文档长度归一化
        """
        self.persist_directory = persist_directory
        self.index_name = index_name
        self.k1 = k1
        self.b = b

        self._corpus: list[str] = []
        self._corpus_ids: list[str] = []
        self._corpus_metadatas: list[dict[str, Any]] = []
        self._tokenized_corpus: list[list[str]] = []
        self._bm25: Any = None
        self._initialized = False

        # 延迟导入 rank_bm25
        self._rank_bm25: Any = None

    def _ensure_bm25_import(self) -> None:
        """确保 rank_bm25 已导入"""
        if self._rank_bm25 is None:
            try:
                from rank_bm25 import BM25Okapi

                self._rank_bm25 = BM25Okapi
            except ImportError as e:
                raise VectorStoreError("rank_bm25 未安装，请运行: uv add rank-bm25") from e

    def _tokenize(self, text: str) -> list[str]:
        """
        简单分词器（可替换为更高级的分词器）

        Args:
            text: 输入文本

        Returns:
            分词列表
        """
        # 简单按空格和标点分词，转换为小写
        import re

        tokens = re.findall(r"\w+", text.lower())
        return tokens

    def _ensure_initialized(self) -> None:
        """确保已初始化"""
        if not self._initialized:
            raise VectorStoreError("BM25IndexStore not initialized. Call initialize() first.")

    def initialize(self) -> None:
        """初始化 BM25 索引"""
        if self._initialized:
            return

        self._ensure_bm25_import()

        try:
            # 确保目录存在
            os.makedirs(self.persist_directory, exist_ok=True)

            # 尝试加载已持久化的索引
            index_file = os.path.join(self.persist_directory, f"{self.index_name}.json")

            if os.path.exists(index_file):
                self._load_from_disk(index_file)
                logger.info(
                    f"BM25IndexStore loaded from {index_file}: {len(self._corpus)} documents"
                )
            else:
                logger.info("BM25IndexStore initialized (empty index)")

            self._initialized = True

        except Exception as e:
            logger.error(f"Failed to initialize BM25IndexStore: {e}")
            raise VectorStoreError(f"Failed to initialize: {e}") from e

    def shutdown(self) -> None:
        """关闭并持久化索引"""
        if self._initialized:
            self._persist_to_disk()
            self._initialized = False
            logger.info("BM25IndexStore shut down")

    def _load_from_disk(self, filepath: str) -> None:
        """从磁盘加载索引数据"""
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        self._corpus = data.get("corpus", [])
        self._corpus_ids = data.get("ids", [])
        self._corpus_metadatas = data.get("metadatas", [])

        # 重新分词并构建 BM25
        self._tokenized_corpus = [self._tokenize(doc) for doc in self._corpus]
        if self._tokenized_corpus:
            self._bm25 = self._rank_bm25(self._tokenized_corpus, k1=self.k1, b=self.b)

    def _persist_to_disk(self) -> None:
        """持久化索引数据到磁盘"""
        if not self._corpus:
            return

        index_file = os.path.join(self.persist_directory, f"{self.index_name}.json")
        data = {
            "corpus": self._corpus,
            "ids": self._corpus_ids,
            "metadatas": self._corpus_metadatas,
        }

        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.debug(f"BM25IndexStore persisted to {index_file}")

    def add(
        self,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        """
        添加文档到 BM25 索引

        Args:
            ids: 文档ID列表
            documents: 文档文本列表
            metadatas: 元数据列表
        """
        self._ensure_initialized()

        if metadatas is None:
            metadatas = [{} for _ in ids]

        try:
            # 添加到语料库
            self._corpus.extend(documents)
            self._corpus_ids.extend(ids)
            self._corpus_metadatas.extend(metadatas)

            # 分词
            new_tokenized = [self._tokenize(doc) for doc in documents]
            self._tokenized_corpus.extend(new_tokenized)

            # 重新构建 BM25 索引
            if self._tokenized_corpus:
                self._bm25 = self._rank_bm25(self._tokenized_corpus, k1=self.k1, b=self.b)

            logger.debug(f"Added {len(ids)} documents to BM25 index (total: {len(self._corpus)})")

            # 立即持久化以确保数据不丢失
            self._persist_to_disk()

        except Exception as e:
            logger.error(f"Failed to add documents to BM25 index: {e}")
            raise VectorStoreError(f"Failed to add documents: {e}") from e

    def search(
        self,
        query: str,
        top_k: int = 5,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        搜索 BM25 索引

        Args:
            query: 查询文本
            top_k: 返回数量
            metadata_filter: 元数据过滤条件（暂不支持）

        Returns:
            搜索结果列表
        """
        self._ensure_initialized()

        if not self._corpus:
            return []

        try:
            # 分词查询
            query_tokens = self._tokenize(query)

            if not query_tokens:
                return []

            # 获取 BM25 分数
            scores = self._bm25.get_scores(query_tokens)

            # 创建 (index, score) 对并排序
            doc_scores = list(enumerate(scores))
            doc_scores.sort(key=lambda x: x[1], reverse=True)

            # 格式化结果
            results = []
            for idx, score in doc_scores[:top_k]:
                # 应用元数据过滤（如果需要）
                if metadata_filter:
                    metadata = self._corpus_metadatas[idx]
                    if not self._matches_filter(metadata, metadata_filter):
                        continue

                results.append(
                    {
                        "id": self._corpus_ids[idx],
                        "text": self._corpus[idx],
                        "score": float(score),
                        "metadata": self._corpus_metadatas[idx],
                    }
                )

            logger.debug(f"BM25 search: query='{query}', found {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Failed to search BM25 index: {e}")
            raise VectorStoreError(f"Failed to search: {e}") from e

    def _matches_filter(self, metadata: dict[str, Any], filter_cond: dict[str, Any]) -> bool:
        """检查元数据是否匹配过滤条件"""
        for key, value in filter_cond.items():
            if key not in metadata or metadata[key] != value:
                return False
        return True

    def delete(self, ids: list[str]) -> None:
        """
        从索引中删除文档

        Args:
            ids: 要删除的文档ID列表
        """
        self._ensure_initialized()

        try:
            ids_set = set(ids)
            indices_to_remove = [
                i for i, doc_id in enumerate(self._corpus_ids) if doc_id in ids_set
            ]

            if not indices_to_remove:
                return

            # 反向排序，以便正确删除
            for idx in sorted(indices_to_remove, reverse=True):
                del self._corpus[idx]
                del self._corpus_ids[idx]
                del self._corpus_metadatas[idx]
                del self._tokenized_corpus[idx]

            # 重新构建索引
            if self._tokenized_corpus:
                self._bm25 = self._rank_bm25(self._tokenized_corpus, k1=self.k1, b=self.b)

            logger.debug(f"Deleted {len(indices_to_remove)} documents from BM25 index")

            # 立即持久化以确保数据不丢失
            self._persist_to_disk()

        except Exception as e:
            logger.error(f"Failed to delete from BM25 index: {e}")
            raise VectorStoreError(f"Failed to delete: {e}") from e

    def get_count(self) -> int:
        """获取索引中的文档数量"""
        self._ensure_initialized()
        return len(self._corpus)

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        try:
            self._ensure_initialized()
            return {
                "type": "bm25",
                "index_name": self.index_name,
                "document_count": len(self._corpus),
                "persist_directory": self.persist_directory,
                "parameters": {
                    "k1": self.k1,
                    "b": self.b,
                },
            }
        except Exception as e:
            logger.error(f"Failed to get BM25 stats: {e}")
            return {"type": "bm25", "error": str(e)}


__all__ = [
    "BM25IndexStore",
]
