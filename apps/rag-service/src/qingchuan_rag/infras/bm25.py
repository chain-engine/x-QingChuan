#!/usr/bin/env python3
"""
BM25 Sparse Index Module

增量式稀疏索引（倒排索引）实现，用于关键词召回，与稠密向量索引互补实现多路召回。

相比全量重建的实现（每次增删都对整个语料重训，O(n)，文档量上千后上传明显变慢），
本模块自研增量维护倒排索引：

- ``_docs: dict[doc_id, _DocEntry]``      文档表（原文、元数据、词频表、词数）
- ``_df: dict[term, int]``                词项文档频率
- ``_postings: dict[term, list[doc_id]]`` 倒排表：词项 → 命中文档

复杂度：
- add / delete：仅增量更新上述统计，O(词数)，与语料总量无关（批量 N 篇 = O(N·词数)）；
- search：仅对倒排表命中的文档打分，O(命中集 × 查询词数)，远小于 O(n)；
- 持久化：快照式（达到变更阈值自动落盘 + shutdown 落盘），避免每次增删全量写盘。

打分采用标准 Okapi BM25：
    idf(t) = ln((N - df(t) + 0.5) / (df(t) + 0.5))
    score(d, q) = Σ_{t∈q} idf(t) * tf(t,d) * (k1 + 1) / (tf(t,d) + k1 * (1 - b + b * dl_d / avgdl))

与 rank_bm25.BM25Okapi 的公式逐项一致，同一语料下分数/排序一致
（见 tests/unit/test_bm25.py 的一致性对比用例）。

线程安全说明：与历史实现一致，本类不做内部加锁；写入（add/delete）与
读取（search）并发由调用方通过 DocumentService/SyncService 的锁协调。
"""

from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass, field
from typing import Any

from qingchuan_rag.core.exceptions import VectorStoreError
from qingchuan_rag.core.logger import logger
from qingchuan_rag.core.paths import resolve_service_path


@dataclass
class _DocEntry:
    """单篇文档的索引条目（增量索引的最小统计单元）。"""

    text: str
    metadata: dict[str, Any]
    term_freq: dict[str, int] = field(default_factory=dict)
    doc_len: int = 0


class BM25IndexStore:
    """
    BM25 稀疏索引存储（增量倒排实现）

    适用于关键词精确匹配和词项召回；add/delete 为 O(词数) 增量操作，
    文档量增长不劣化写入与查询路径。
    """

    def __init__(
        self,
        persist_directory: str = "./data/bm25",
        index_name: str = "default",
        k1: float = 1.5,
        b: float = 0.75,
        persist_every: int = 50,
    ):
        """
        Args:
            persist_directory: 持久化存储目录
            index_name: 索引名称
            k1: BM25 参数，控制词频饱和度
            b: BM25 参数，控制文档长度归一化
            persist_every: 累计变更条数达到该值自动落盘一次（0 表示每次变更立即落盘）
        """
        # 相对路径锚定到服务根目录（apps/rag-service/data），避免随 CWD 漂移写入仓库根目录
        self.persist_directory = resolve_service_path(persist_directory)
        self.index_name = index_name
        self.k1 = k1
        self.b = b
        self.persist_every = max(0, persist_every)

        self._docs: dict[str, _DocEntry] = {}
        self._df: dict[str, int] = {}
        self._postings: dict[str, list[str]] = {}
        self._total_terms: int = 0
        self._changes_since_persist: int = 0
        self._initialized = False

    def _tokenize(self, text: str) -> list[str]:
        """轻量分词器（无词典，中文按双字 bigram 切分）。

        - 英文 / 数字串：整词保留（``[a-z0-9]+``）；
        - 中文连续串：按双字 bigram 切分（如 "人社数据" → "人社" "社数" "数据"），
          覆盖中文查询词级匹配，无需引入 jieba 等词典依赖。

        背景：单纯 ``\\w+`` 会把整段连续中文匹配成单个 token，导致中文查询
        无法命中任何文档（旧实现靠"全量返回 0 分"兜底，检索质量为零）。
        """
        tokens: list[str] = []
        for chunk in re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", text.lower()):
            if re.fullmatch(r"[a-z0-9]+", chunk):
                tokens.append(chunk)
            elif len(chunk) == 1:
                tokens.append(chunk)
            else:
                # 双字 bigram；首尾单字补入以覆盖单字查询
                tokens.extend(chunk[i : i + 2] for i in range(len(chunk) - 1))
                tokens.append(chunk[0])
                tokens.append(chunk[-1])
        return tokens

    def _ensure_initialized(self) -> None:
        """确保已初始化。"""
        if not self._initialized:
            raise VectorStoreError("BM25IndexStore not initialized. Call initialize() first.")

    # ----------------------------------------------------------
    # 生命周期
    # ----------------------------------------------------------

    def initialize(self) -> None:
        """初始化 BM25 索引（加载已持久化的索引）。"""
        if self._initialized:
            return

        try:
            os.makedirs(self.persist_directory, exist_ok=True)
            index_file = os.path.join(self.persist_directory, f"{self.index_name}.json")
            if os.path.exists(index_file):
                self._load_from_disk(index_file)
                logger.info(f"BM25IndexStore loaded from {index_file}: {len(self._docs)} documents")
            else:
                logger.info("BM25IndexStore initialized (empty index)")
            self._initialized = True
        except Exception as e:
            logger.error(f"Failed to initialize BM25IndexStore: {e}")
            raise VectorStoreError(f"Failed to initialize: {e}") from e

    def shutdown(self) -> None:
        """关闭并持久化索引。"""
        if self._initialized:
            self._persist_to_disk()
            self._initialized = False
            logger.info("BM25IndexStore shut down")

    def _load_from_disk(self, filepath: str) -> None:
        """从磁盘加载索引数据。

        兼容两种格式：
        - 增量格式（含 term_freq / doc_len）：直接恢复统计；
        - 旧全量重建格式（corpus / ids / metadatas）：启动时一次性重建统计（O(n) 仅一次）。
        """
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        documents = data.get("documents")
        if documents:
            # 增量格式：直接恢复
            for item in documents:
                doc_id: str = item["id"]
                self._docs[doc_id] = _DocEntry(
                    text=item["text"],
                    metadata=item.get("metadata", {}),
                    term_freq=item.get("term_freq", {}),
                    doc_len=item.get("doc_len", 0),
                )
                for term in self._docs[doc_id].term_freq:
                    self._df[term] = self._df.get(term, 0) + 1
                    self._postings.setdefault(term, []).append(doc_id)
                self._total_terms += self._docs[doc_id].doc_len
        else:
            # 旧格式：corpus / ids / metadatas → 重建分词与统计（仅启动时一次）
            corpus: list[str] = data.get("corpus", [])
            ids: list[str] = data.get("ids", [])
            metadatas: list[dict[str, Any]] = data.get("metadatas", [])
            for doc_id, doc, meta in zip(ids, corpus, metadatas, strict=False):
                tokens = self._tokenize(doc)
                term_freq: dict[str, int] = {}
                for term in tokens:
                    term_freq[term] = term_freq.get(term, 0) + 1
                self._docs[doc_id] = _DocEntry(
                    text=doc, metadata=meta, term_freq=term_freq, doc_len=len(tokens)
                )
                for term in term_freq:
                    self._df[term] = self._df.get(term, 0) + 1
                    self._postings.setdefault(term, []).append(doc_id)
                self._total_terms += len(tokens)

    def _persist_to_disk(self) -> None:
        """持久化索引数据到磁盘（快照式，O(n) 仅在落盘时发生）。"""
        if not self._docs:
            return

        index_file = os.path.join(self.persist_directory, f"{self.index_name}.json")
        data = {
            "index_name": self.index_name,
            "k1": self.k1,
            "b": self.b,
            "documents": [
                {
                    "id": doc_id,
                    "text": entry.text,
                    "metadata": entry.metadata,
                    "term_freq": entry.term_freq,
                    "doc_len": entry.doc_len,
                }
                for doc_id, entry in self._docs.items()
            ],
        }

        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        self._changes_since_persist = 0
        logger.debug(f"BM25IndexStore persisted to {index_file}")

    def _mark_changed(self, count: int) -> None:
        """累计变更并触发阈值落盘（persist_every=0 时每次立即落盘）。"""
        if self.persist_every == 0:
            self._persist_to_disk()
            return
        self._changes_since_persist += count
        if self._changes_since_persist >= self.persist_every:
            self._persist_to_disk()

    # ----------------------------------------------------------
    # 写入：增量维护倒排索引
    # ----------------------------------------------------------

    def add(
        self,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        """增量添加文档到 BM25 索引（同 id 重复添加为幂等覆盖）。

        Args:
            ids: 文档ID列表
            documents: 文档文本列表
            metadatas: 元数据列表
        """
        self._ensure_initialized()

        if metadatas is None:
            metadatas = [{} for _ in ids]

        try:
            for doc_id, doc, meta in zip(ids, documents, metadatas, strict=False):
                # 同 id 重复写入：先移除旧条目再插入，保证幂等
                if doc_id in self._docs:
                    self._remove_doc(doc_id)

                tokens = self._tokenize(doc)
                term_freq: dict[str, int] = {}
                for term in tokens:
                    term_freq[term] = term_freq.get(term, 0) + 1

                self._docs[doc_id] = _DocEntry(
                    text=doc, metadata=meta, term_freq=term_freq, doc_len=len(tokens)
                )
                self._total_terms += len(tokens)
                for term in term_freq:
                    self._df[term] = self._df.get(term, 0) + 1
                    self._postings.setdefault(term, []).append(doc_id)

            self._mark_changed(len(ids))
            logger.debug(f"Added {len(ids)} documents to BM25 index (total: {len(self._docs)})")
        except Exception as e:
            logger.error(f"Failed to add documents to BM25 index: {e}")
            raise VectorStoreError(f"Failed to add documents: {e}") from e

    def delete(self, ids: list[str]) -> None:
        """增量删除文档并同步更新倒排统计。

        Args:
            ids: 要删除的文档ID列表
        """
        self._ensure_initialized()

        try:
            removed = 0
            for doc_id in set(ids):
                if self._remove_doc(doc_id):
                    removed += 1
            if removed:
                self._mark_changed(removed)
                logger.debug(f"Deleted {removed} documents from BM25 index")
        except Exception as e:
            logger.error(f"Failed to delete from BM25 index: {e}")
            raise VectorStoreError(f"Failed to delete: {e}") from e

    def _remove_doc(self, doc_id: str) -> bool:
        """移除单篇文档并回退 df / postings / 总词数统计。"""
        entry = self._docs.pop(doc_id, None)
        if entry is None:
            return False

        self._total_terms -= entry.doc_len
        for term in entry.term_freq:
            self._df[term] -= 1
            if self._df[term] <= 0:
                del self._df[term]
            post = self._postings.get(term)
            if post is not None:
                try:
                    post.remove(doc_id)
                except ValueError:
                    pass
                if not post:
                    del self._postings[term]
        return True

    # ----------------------------------------------------------
    # 读取
    # ----------------------------------------------------------

    def search(
        self,
        query: str,
        top_k: int = 5,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """搜索 BM25 索引（仅对倒排命中的文档打分）。

        Args:
            query: 查询文本
            top_k: 返回数量
            metadata_filter: 元数据过滤条件（等值匹配，取交集）

        Returns:
            搜索结果列表 [{"id", "text", "score", "metadata"}, ...]
        """
        self._ensure_initialized()

        if not self._docs:
            return []

        try:
            query_tokens = self._tokenize(query)
            if not query_tokens:
                return []

            # 候选文档 = 所有查询词倒排表的并集（远小于全语料）
            candidates: set[str] = set()
            for term in query_tokens:
                candidates.update(self._postings.get(term, ()))
            if not candidates:
                return []

            doc_count = len(self._docs)
            avgdl = self._total_terms / doc_count if doc_count else 0.0
            k1, b = self.k1, self.b

            scored: list[tuple[float, str]] = []
            for doc_id in candidates:
                entry = self._docs[doc_id]
                # 与 rank_bm25 一致：query 词逐项累加（不去重），tf 缺失不计
                score = 0.0
                if avgdl > 0:
                    norm = k1 * (1 - b + b * entry.doc_len / avgdl)
                    for term in query_tokens:
                        tf = entry.term_freq.get(term, 0)
                        if not tf:
                            continue
                        df = self._df.get(term, 0)
                        if df <= 0:
                            continue
                        idf = math.log((doc_count - df + 0.5) / (df + 0.5))
                        score += idf * (tf * (k1 + 1)) / (tf + norm)
                scored.append((score, doc_id))

            scored.sort(key=lambda x: x[0], reverse=True)

            results: list[dict[str, Any]] = []
            for score, doc_id in scored:
                if len(results) >= top_k:
                    break
                entry = self._docs[doc_id]
                if metadata_filter and not self._matches_filter(entry.metadata, metadata_filter):
                    continue
                results.append(
                    {
                        "id": doc_id,
                        "text": entry.text,
                        "score": float(score),
                        "metadata": entry.metadata,
                    }
                )

            logger.debug(f"BM25 search: query='{query}', found {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Failed to search BM25 index: {e}")
            raise VectorStoreError(f"Failed to search: {e}") from e

    def get_all(self) -> list[dict[str, Any]]:
        """返回全部索引条目（管理面用：按文档 ID 清理 / 查询，非检索路径）。"""
        self._ensure_initialized()
        return [
            {"id": doc_id, "text": entry.text, "score": 0.0, "metadata": entry.metadata}
            for doc_id, entry in self._docs.items()
        ]

    def _matches_filter(self, metadata: dict[str, Any], filter_cond: dict[str, Any]) -> bool:
        """检查元数据是否匹配过滤条件（等值交集）。"""
        for key, value in filter_cond.items():
            if key not in metadata or metadata[key] != value:
                return False
        return True

    def get_count(self) -> int:
        """获取索引中的文档数量。"""
        self._ensure_initialized()
        return len(self._docs)

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息。"""
        try:
            self._ensure_initialized()
            return {
                "type": "bm25",
                "index_name": self.index_name,
                "document_count": len(self._docs),
                "term_count": len(self._df),
                "persist_directory": self.persist_directory,
                "parameters": {
                    "k1": self.k1,
                    "b": self.b,
                    "persist_every": self.persist_every,
                },
            }
        except Exception as e:
            logger.error(f"Failed to get BM25 stats: {e}")
            return {"type": "bm25", "error": str(e)}


__all__ = [
    "BM25IndexStore",
]
