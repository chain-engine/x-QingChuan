"""BM25 增量索引单元测试。

重点覆盖：
- 增量 add/delete 的正确性（多次增量写入、删除后统计回退）；
- 同 id 幂等覆盖；
- 与 rank_bm25.BM25Okapi 在同一语料下的打分一致性（公式逐项一致）；
- 持久化 round-trip（含旧格式兼容）；
- 按文档 ID 删除（原"空查询取全部"hack 已废弃，改 get_all）。
"""
from __future__ import annotations

import json
import shutil
import tempfile

import pytest
from rank_bm25 import BM25Okapi

from qingchuan_rag.infras.bm25 import BM25IndexStore
from qingchuan_rag.repositories.bm25_repository import BM25Repository

CORPUS = [
    "晴川项目是面向人社场景的检索增强生成系统",
    "它包含离线数据同步、语义检索与生成问答三大能力",
    "数据从人社 API 拉取后进入向量库进行索引",
    "检索阶段采用多路召回与重排，BM25 负责稀疏检索",
    "向量检索负责稠密召回，生成阶段由大模型基于检索结果作答",
    "Python programming language is widely used in data science",
    "Machine learning models need large amounts of training data",
    "The quick brown fox jumps over the lazy dog",
]


@pytest.fixture
def temp_dir():
    path = tempfile.mkdtemp()
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def store(temp_dir):
    store = BM25IndexStore(
        persist_directory=temp_dir, index_name="test", persist_every=0  # 每次落盘，便于断言
    )
    store.initialize()
    yield store
    store.shutdown()


def _add_docs(store: BM25IndexStore, ids: list[str], texts: list[str]) -> None:
    store.add(ids, texts, [{"document_id": i.split("_")[0]} for i in ids])


class TestIncrementalAddSearch:
    def test_add_then_search(self, store: BM25IndexStore) -> None:
        _add_docs(store, [f"doc_{i}" for i in range(4)], CORPUS[:4])
        results = store.search("人社", top_k=10)
        # CORPUS[0] 与 CORPUS[2] 均含"人社"
        assert {r["id"] for r in results} >= {"doc_0", "doc_2"}

    def test_multiple_incremental_adds(self, store: BM25IndexStore) -> None:
        # 分多次增量写入（模拟批量上传分片）
        for i in range(0, len(CORPUS), 3):
            _add_docs(store, [f"doc_{j}" for j in range(i, min(i + 3, len(CORPUS)))], CORPUS[i : i + 3])
        assert store.get_count() == len(CORPUS)
        results = store.search("检索", top_k=10)
        assert len(results) >= 2  # doc_0 与 doc_3 均含"检索"

    def test_upsert_same_id_is_idempotent(self, store: BM25IndexStore) -> None:
        _add_docs(store, ["doc_1"], [CORPUS[0]])
        _add_docs(store, ["doc_1"], [CORPUS[1]])  # 同 id 覆盖
        assert store.get_count() == 1
        results = store.search("检索增强生成系统", top_k=5)
        assert results[0]["id"] == "doc_1"
        assert "离线数据同步" in results[0]["text"]  # 已被新内容覆盖

    def test_empty_query_returns_empty(self, store: BM25IndexStore) -> None:
        _add_docs(store, ["doc_1"], [CORPUS[0]])
        assert store.search("", top_k=5) == []

    def test_no_match_returns_empty(self, store: BM25IndexStore) -> None:
        _add_docs(store, ["doc_1"], [CORPUS[0]])
        assert store.search("不存在词项xyz", top_k=5) == []


class TestDelete:
    def test_delete_removes_from_index(self, store: BM25IndexStore) -> None:
        _add_docs(store, [f"doc_{i}" for i in range(4)], CORPUS[:4])
        assert store.search("人社", top_k=10)
        store.delete(["doc_0"])
        # doc_2 仍含"人社"，但 doc_0 必须不再出现
        results = store.search("人社", top_k=10)
        assert "doc_0" not in {r["id"] for r in results}
        assert store.get_count() == 3

    def test_delete_updates_stats_correctly(self, store: BM25IndexStore) -> None:
        _add_docs(store, [f"doc_{i}" for i in range(8)], CORPUS)
        stats_before = store.get_stats()
        store.delete(["doc_0", "doc_1"])
        stats_after = store.get_stats()
        assert stats_after["document_count"] == stats_before["document_count"] - 2
        # 删除后其余文档仍可正常检索
        assert store.search("向量检索", top_k=5)
        assert store.search("machine learning", top_k=5)

    def test_delete_nonexistent_is_noop(self, store: BM25IndexStore) -> None:
        _add_docs(store, ["doc_1"], [CORPUS[0]])
        store.delete(["doc_missing"])
        assert store.get_count() == 1


class TestConsistencyWithRankBM25:
    """自研打分与 rank_bm25.BM25Okapi 在同一语料下逐分一致（公式逐项一致）。"""

    def test_scores_match_rank_bm25(self, store: BM25IndexStore) -> None:
        # 与 store 使用同一分词逻辑（含中文 bigram），保证可比
        tokenized_corpus = [store._tokenize(doc) for doc in CORPUS]
        reference = BM25Okapi(tokenized_corpus, k1=1.5, b=0.75)

        _add_docs(store, [f"doc_{i}" for i in range(len(CORPUS))], CORPUS)
        query = "检索 向量 人社 data science"
        query_tokens = store._tokenize(query)

        expected = reference.get_scores(query_tokens)
        results = store.search(query, top_k=len(CORPUS))
        actual = {r["id"]: r["score"] for r in results}

        for i, exp in enumerate(expected):
            doc_id = f"doc_{i}"
            if doc_id in actual:
                # 返回的文档分数必须与 rank_bm25 逐项一致
                assert actual[doc_id] == pytest.approx(exp, rel=1e-6), f"doc_{i} 分数不一致"
            else:
                # 未返回的文档只能是 rank_bm25 中 ≤0 分的（未命中或 idf=0）
                assert exp <= 0, f"doc_{i} 应为正分但未返回"

    def test_ranking_order_matches(self, store: BM25IndexStore) -> None:
        tokenized_corpus = [store._tokenize(doc) for doc in CORPUS]
        reference = BM25Okapi(tokenized_corpus, k1=1.5, b=0.75)

        _add_docs(store, [f"doc_{i}" for i in range(len(CORPUS))], CORPUS)
        query = "检索 生成 数据 model"
        query_tokens = store._tokenize(query)

        expected_order = [
            i
            for i, _ in sorted(
                enumerate(reference.get_scores(query_tokens)), key=lambda x: x[1], reverse=True
            )
        ]
        actual_order = [int(r["id"].split("_")[1]) for r in store.search(query, top_k=5)]
        assert actual_order == expected_order[:5]


class TestPersistence:
    def test_roundtrip(self, temp_dir: str) -> None:
        store = BM25IndexStore(persist_directory=temp_dir, index_name="test")
        store.initialize()
        _add_docs(store, [f"doc_{i}" for i in range(4)], CORPUS[:4])
        store.shutdown()  # shutdown 触发落盘

        reloaded = BM25IndexStore(persist_directory=temp_dir, index_name="test")
        reloaded.initialize()
        assert reloaded.get_count() == 4
        results = reloaded.search("人社", top_k=10)
        assert "doc_0" in {r["id"] for r in results}
        # 重启后仍可增量写入
        _add_docs(reloaded, ["doc_new"], [CORPUS[4]])
        assert reloaded.get_count() == 5
        reloaded.shutdown()

    def test_loads_legacy_format(self, temp_dir: str) -> None:
        """兼容旧全量重建格式（corpus/ids/metadatas），升级无需重建索引。"""
        legacy = {
            "corpus": CORPUS[:3],
            "ids": ["legacy_0", "legacy_1", "legacy_2"],
            "metadatas": [{"document_id": "legacy"}] * 3,
        }
        index_file = tempfile.mkdtemp()
        with open(f"{index_file}/test.json", "w", encoding="utf-8") as f:
            json.dump(legacy, f, ensure_ascii=False)

        store = BM25IndexStore(persist_directory=index_file, index_name="test")
        store.initialize()
        assert store.get_count() == 3
        # CORPUS[0] 与 CORPUS[2] 均含"人社"
        assert {"legacy_0", "legacy_2"} <= {r["id"] for r in store.search("人社", top_k=10)}
        store.shutdown()
        shutil.rmtree(index_file, ignore_errors=True)

    def test_auto_persist_threshold(self, temp_dir: str) -> None:
        """达到变更阈值自动落盘，未达阈值仅 shutdown 落盘。"""
        store = BM25IndexStore(persist_directory=temp_dir, index_name="test", persist_every=3)
        store.initialize()
        _add_docs(store, ["d1", "d2"], CORPUS[:2])  # 2 次变更，未达阈值
        index_file = f"{temp_dir}/test.json"
        assert not __import__("os").path.exists(index_file)
        _add_docs(store, ["d3"], [CORPUS[2]])  # 累计 3 次，触发落盘
        assert __import__("os").path.exists(index_file)
        store.shutdown()


class TestMetadataFilter:
    def test_filter_by_document_id(self, store: BM25IndexStore) -> None:
        _add_docs(store, [f"doc_{i}" for i in range(4)], CORPUS[:4])
        results = store.search("检索", top_k=10, metadata_filter={"document_id": "doc_1"})
        assert all(r["metadata"]["document_id"] == "doc_1" for r in results)


class TestRepositoryDeleteByDocumentId:
    def test_delete_by_document_id_removes_all_chunks(self, temp_dir: str) -> None:
        repo = BM25Repository(persist_directory=temp_dir, index_name="test")
        repo.initialize()
        chunk_ids = [f"{doc}_chunk_{i}" for doc in ("doc_a", "doc_b") for i in range(3)]
        texts = CORPUS[:6]
        repo.add(
            chunk_ids,
            texts,
            [{"document_id": cid.rsplit("_", 2)[0]} for cid in chunk_ids],
        )
        removed = repo.delete_by_document_id("doc_a")
        assert removed == 3
        assert repo.get_count() == 3
        assert repo.get_by_document_id("doc_a") == []
        assert len(repo.get_by_document_id("doc_b")) == 3
        repo.shutdown()
