"""
MilvusVectorStore 集成 / 单元测试

覆盖：milvus-lite 本地文件模式下的初始化、写入、检索（含元数据过滤）、
删除（按 id / 按元数据）、按元数据取回、计数、自动建集、距离语义对齐，
以及 filter 表达式构造与转义；另覆盖 VectorRepository 的 milvus 分发链路。
"""

import shutil
import tempfile
from pathlib import Path

import pytest

from qingchuan_rag.core.exceptions import VectorStoreError
from qingchuan_rag.infras.vector import MilvusVectorStore

# 3 维测试向量（未归一化，COSINE 度量下仅方向影响相似度）
V_A = [1.0, 0.0, 0.0]
V_NEAR_A = [0.9, 0.1, 0.0]
V_B = [0.0, 1.0, 0.0]
V_C = [0.0, 0.0, 1.0]


class TestMilvusVectorStoreIntegration:
    """MilvusVectorStore 集成测试（milvus-lite 临时文件库）"""

    @pytest.fixture
    def temp_dir(self):
        temp_path = tempfile.mkdtemp()
        yield temp_path
        shutil.rmtree(temp_path, ignore_errors=True)

    @pytest.fixture
    def store(self, temp_dir):
        """显式维度建集（dimension=3，initialize 即建集合）"""
        store = MilvusVectorStore(
            uri=str(Path(temp_dir) / "milvus.db"),
            collection_name="documents",
            metric_type="cosine",
            dimension=3,
        )
        store.initialize()
        yield store
        store.shutdown()

    def test_initialize_and_stats(self, store):
        """初始化后集合存在，count=0，stats 类型为 milvus"""
        assert store.get_count() == 0
        stats = store.get_stats()
        assert stats["type"] == "milvus"
        assert stats["count"] == 0
        assert stats["collection"] == "documents"

    def test_add_and_search_structure(self, store):
        """写入后可检索，返回结构 {id, text, metadata, distance} 且元数据随结果带回"""
        ids = ["a-1", "a-2", "b-1"]
        embeddings = [V_A, V_NEAR_A, V_B]
        texts = ["text a1", "text a2", "text b1"]
        metadatas = [
            {"document_id": "doc-a", "chunk_index": 1},
            {"document_id": "doc-a", "chunk_index": 2},
            {"document_id": "doc-b", "chunk_index": 1},
        ]
        store.add(ids, embeddings, texts, metadatas)

        results = store.search(query_embedding=V_A, top_k=3)
        assert len(results) == 3

        # 结构字段齐全
        first = results[0]
        assert set(first.keys()) == {"id", "text", "metadata", "distance"}
        # 与查询向量完全一致的向量应排在最前，且 distance ≈ 0（距离语义：小=相似）
        assert first["id"] == "a-1"
        assert first["distance"] == pytest.approx(0.0, abs=1e-3)
        # 动态元数据字段随 search 结果返回（与 Chroma 输出对齐）
        assert first["metadata"]["document_id"] == "doc-a"

        # 相似度递减（距离递增）
        distances = [r["distance"] for r in results]
        assert distances == sorted(distances)

    def test_search_metadata_filter(self, store):
        """where 过滤：只返回命中文档的 chunks"""
        ids = ["a-1", "a-2", "b-1"]
        embeddings = [V_A, V_NEAR_A, V_B]
        texts = ["text a1", "text a2", "text b1"]
        metadatas = [
            {"document_id": "doc-a", "chunk_index": 1},
            {"document_id": "doc-a", "chunk_index": 2},
            {"document_id": "doc-b", "chunk_index": 1},
        ]
        store.add(ids, embeddings, texts, metadatas)

        results = store.search(query_embedding=V_A, top_k=10, where={"document_id": "doc-b"})
        assert [r["id"] for r in results] == ["b-1"]
        assert results[0]["metadata"]["document_id"] == "doc-b"

    def test_bool_metadata_filter_end_to_end(self, store):
        """布尔元数据过滤端到端（Milvus filter 布尔字面量为小写 true/false）"""
        store.add(
            ["b-true", "b-false"],
            [V_A, V_B],
            ["active doc", "inactive doc"],
            [{"active": True}, {"active": False}],
        )
        results = store.search(query_embedding=V_A, top_k=10, where={"active": True})
        assert [r["id"] for r in results] == ["b-true"]

    def test_auto_create_collection_without_dimension(self, temp_dir):
        """未传 dimension 时，首条 add 自动建集并检索"""
        store = MilvusVectorStore(
            uri=str(Path(temp_dir) / "auto.db"),
            collection_name="auto_docs",
            metric_type="cosine",
        )
        store.initialize()
        assert store.get_count() == 0

        store.add(["auto-1"], [V_A], ["auto text"], [{"document_id": "auto-doc"}])
        assert store.get_count() == 1

        results = store.search(query_embedding=V_A, top_k=1)
        assert len(results) == 1
        assert results[0]["id"] == "auto-1"
        assert results[0]["metadata"]["document_id"] == "auto-doc"
        store.shutdown()

    def test_delete_by_ids(self, store):
        """按主键删除向量"""
        store.add(["d-1", "d-2"], [V_A, V_B], ["t1", "t2"])
        store.delete(["d-1"])
        results = store.search(query_embedding=V_A, top_k=10)
        assert [r["id"] for r in results] == ["d-2"]

    def test_delete_by_metadata(self, store):
        """按元数据等值条件删除，返回删除数量"""
        store.add(
            ["a-1", "a-2", "b-1"],
            [V_A, V_NEAR_A, V_B],
            ["ta1", "ta2", "tb1"],
            [
                {"document_id": "doc-a"},
                {"document_id": "doc-a"},
                {"document_id": "doc-b"},
            ],
        )
        deleted = store.delete_by_metadata({"document_id": "doc-a"})
        assert deleted == 2
        assert store.get_count() == 1
        # 删除后按元数据取回为空
        assert store.get_by_metadata({"document_id": "doc-a"}) == []

    def test_get_by_metadata(self, store):
        """按元数据取回 chunks（含 text 与动态字段），不构造查询向量"""
        store.add(
            [f"doc-a-{i}" for i in range(2)] + ["doc-b-0"],
            [V_A, V_NEAR_A, V_B],
            ["text-a-0", "text-a-1", "text-b-0"],
            [{"document_id": "doc-a"}, {"document_id": "doc-a"}, {"document_id": "doc-b"}],
        )
        chunks = store.get_by_metadata({"document_id": "doc-a"})
        assert {c["id"] for c in chunks} == {"doc-a-0", "doc-a-1"}
        assert {c["text"] for c in chunks} == {"text-a-0", "text-a-1"}
        assert all(c["metadata"]["document_id"] == "doc-a" for c in chunks)
        assert store.get_by_metadata({"document_id": "missing"}) == []

    def test_shutdown_after_search_raises(self, store):
        """shutdown 后再次访问应报错（未初始化）"""
        store.add(["s-1"], [V_A], ["text"])
        store.shutdown()
        with pytest.raises(VectorStoreError):
            store.search(query_embedding=V_A, top_k=1)


class TestMilvusVectorStoreUnit:
    """MilvusVectorStore 单元测试（filter 表达式构造）"""

    @pytest.fixture
    def store(self):
        return MilvusVectorStore(uri="http://milvus:19530", collection_name="documents")

    def test_build_filter_expr_none(self, store):
        """空过滤条件返回空表达式"""
        assert store._build_filter_expr(None) == ""
        assert store._build_filter_expr({}) == ""

    def test_build_filter_expr_string_escaping(self, store):
        """字符串值转义引号与反斜杠，防 filter 注入"""
        expr = store._build_filter_expr({"document_id": 'doc"a\\b'})
        assert expr == 'document_id == "doc\\"a\\\\b"'

    def test_build_filter_expr_scalar_types(self, store):
        """int / float 不加引号；bool 输出 Milvus 小写字面量 true/false（Python bool 是 int 子类，须前置判断）"""
        assert store._build_filter_expr({"chunk_index": 2}) == "chunk_index == 2"
        assert store._build_filter_expr({"score": 0.85}) == "score == 0.85"
        assert store._build_filter_expr({"flag": True}) == "flag == true"
        assert store._build_filter_expr({"flag": False}) == "flag == false"

    def test_build_filter_expr_multi_and(self, store):
        """多条件 AND 拼接"""
        expr = store._build_filter_expr({"document_id": "doc-a", "chunk_index": 1})
        assert expr == 'document_id == "doc-a" and chunk_index == 1'


class TestVectorRepositoryMilvusIntegration:
    """VectorRepository 的 milvus 分发链路（store_type=milvus）"""

    @pytest.fixture
    def temp_dir(self):
        temp_path = tempfile.mkdtemp()
        yield temp_path
        shutil.rmtree(temp_path, ignore_errors=True)

    @pytest.fixture
    def repo(self, temp_dir):
        from qingchuan_rag.repositories.vector_repository import VectorRepository

        repo = VectorRepository(
            store_type="milvus",
            milvus_uri=str(Path(temp_dir) / "repo.db"),
            collection_name="repo_docs",
            distance_type="cosine",
            dimension=3,
            milvus_token="test-token",
            milvus_username="root",
            milvus_password="secret",
        )
        repo.initialize()
        yield repo
        repo.shutdown()

    def test_milvus_dispatch_add_search(self, repo):
        """经仓储层完成 milvus 写入与检索，score 为相似度语义"""
        repo.add(
            ["r-1", "r-2"],
            [V_A, V_B],
            ["repo text a", "repo text b"],
            [{"document_id": "rdoc-1"}, {"document_id": "rdoc-1"}],
        )
        results = repo.search(query_embedding=V_A, top_k=2)
        assert len(results) == 2
        # 最相似向量 score 最高
        assert results[0]["id"] == "r-1"
        assert results[0]["score"] >= results[1]["score"]
        assert repo.get_count() == 2

    def test_milvus_repo_delete_by_document_id(self, repo):
        """按文档 ID 删除向量（仓库层透传元数据过滤）"""
        repo.add(
            ["r-a-0", "r-a-1", "r-b-0"],
            [V_A, V_NEAR_A, V_B],
            ["ta", "ta", "tb"],
            [
                {"document_id": "rdoc-a"},
                {"document_id": "rdoc-a"},
                {"document_id": "rdoc-b"},
            ],
        )
        assert repo.delete_by_document_id("rdoc-a") == 2
        assert repo.get_count() == 1
        assert repo.get_by_document_id("rdoc-a") == []
        assert len(repo.get_by_document_id("rdoc-b")) == 1
