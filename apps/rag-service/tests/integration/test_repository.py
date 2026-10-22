"""
Document Repository Integration Tests
"""

import shutil
import tempfile

import pytest

from qingchuan_rag.repositories.document_repository import DocumentRepository


class TestDocumentRepositoryIntegration:
    """Integration tests for DocumentRepository"""

    @pytest.fixture
    def temp_storage(self):
        """Create temporary storage directory"""
        temp_path = tempfile.mkdtemp()
        yield temp_path
        shutil.rmtree(temp_path, ignore_errors=True)

    @pytest.fixture
    def repository(self, temp_storage):
        """Create repository with temp storage"""
        from qingchuan_rag.infras.storage import LocalStorage

        repo = DocumentRepository(storage=LocalStorage(base_dir=temp_storage))
        repo.initialize()
        yield repo
        repo.shutdown()

    def test_save_and_load_document(self, repository):
        """Test saving and loading a document"""
        doc = {
            "document_id": "test-doc-1",
            "content": "Test content",
            "metadata": {"source": "test"},
        }
        repository.save(doc)
        loaded = repository.load("test-doc-1")
        assert loaded is not None
        assert loaded["document_id"] == "test-doc-1"
        # 非列字段并入 metadata（SQLAlchemy 版存储语义）
        assert loaded["metadata"]["content"] == "Test content"

    def test_document_not_found(self, repository):
        """Test loading non-existent document"""
        result = repository.load("nonexistent")
        assert result is None

    def test_delete_document(self, repository):
        """Test deleting a document"""
        doc = {"document_id": "test-doc-delete", "content": "To be deleted"}
        repository.save(doc)
        assert repository.load("test-doc-delete") is not None
        repository.delete("test-doc-delete")
        assert repository.load("test-doc-delete") is None

    def test_list_all_documents(self, repository):
        """Test listing all documents"""
        docs = [{"document_id": f"doc-{i}", "content": f"Content {i}"} for i in range(3)]
        for doc in docs:
            repository.save(doc)
        all_docs = repository.list_all()
        assert len(all_docs) >= 3

    def test_list_page_pagination_and_filter(self, repository):
        """存储层分页：窗口切片 + 状态/类型过滤（不再全量加载后内存切片）"""
        for i in range(10):
            repository.save(
                {
                    "document_id": f"page-doc-{i}",
                    "content": f"Content {i}",
                    "status": "completed" if i % 2 == 0 else "failed",
                    "file_type": "txt",
                }
            )

        # 分页窗口：limit 只返回窗口内条数
        page1, total = repository.list_page(skip=0, limit=4)
        assert total >= 10
        assert len(page1) == 4

        # 翻页无重叠
        page2, _ = repository.list_page(skip=4, limit=4)
        assert len(page2) == 4
        assert {d["document_id"] for d in page1}.isdisjoint(
            {d["document_id"] for d in page2}
        )

        # skip 越界返回空页
        beyond, total_beyond = repository.list_page(skip=100, limit=4)
        assert beyond == []
        assert total_beyond >= 10

        # 状态过滤（total 为过滤后的匹配数）
        completed, total_completed = repository.list_page(status="completed")
        assert total_completed >= 5
        assert all(d["status"] == "completed" for d in completed)

        # 过滤 + 分页组合
        failed_page, total_failed = repository.list_page(
            status="failed", skip=0, limit=2
        )
        assert total_failed >= 5
        assert len(failed_page) == 2
        assert all(d["status"] == "failed" for d in failed_page)

        # 不匹配的类型
        _, total_pdf = repository.list_page(file_type="pdf")
        assert total_pdf == 0

    def test_exists_check(self, repository):
        """Test document existence check"""
        doc = {"document_id": "test-exists", "content": "Test"}
        assert not repository.exists("test-exists")
        repository.save(doc)
        assert repository.exists("test-exists")

    def test_update_document(self, repository):
        """Test updating a document"""
        doc = {"document_id": "test-update", "content": "Original", "version": 1}
        repository.save(doc)
        repository.update("test-update", {"content": "Updated", "version": 2})
        loaded = repository.load("test-update")
        assert loaded["metadata"]["content"] == "Updated"
        assert loaded["metadata"]["version"] == 2

    def test_stats(self, repository):
        """Test getting repository stats"""
        doc = {"document_id": "test-stats", "content": "Stats test"}
        repository.save(doc)
        stats = repository.get_stats()
        assert "type" in stats
        assert stats["document_count"] >= 1


class TestVectorRepositoryIntegration:
    """Integration tests for VectorRepository"""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory"""
        temp_path = tempfile.mkdtemp()
        yield temp_path
        shutil.rmtree(temp_path, ignore_errors=True)

    @pytest.fixture
    def vector_repo(self, temp_dir):
        """Create vector repository"""
        from qingchuan_rag.repositories.vector_repository import VectorRepository

        repo = VectorRepository(persist_directory=temp_dir, collection_name="test_collection")
        repo.initialize()
        yield repo
        repo.shutdown()

    def test_add_and_search_vectors(self, vector_repo):
        """Test adding and searching vectors"""
        ids = ["vec-1", "vec-2"]
        embeddings = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        texts = ["First text", "Second text"]
        vector_repo.add(ids, embeddings, texts)

        results = vector_repo.search(query_embedding=[0.1, 0.2, 0.3], top_k=2)
        assert len(results) >= 1

    def test_vector_count(self, vector_repo):
        """Test getting vector count"""
        initial_count = vector_repo.get_count()
        ids = ["vec-new"]
        embeddings = [[0.1, 0.2, 0.3]]
        texts = ["New text"]
        vector_repo.add(ids, embeddings, texts)
        new_count = vector_repo.get_count()
        assert new_count == initial_count + 1

    def test_delete_vectors(self, vector_repo):
        """Test deleting vectors"""
        ids = ["vec-to-delete"]
        embeddings = [[0.1, 0.2, 0.3]]
        texts = ["To be deleted"]
        vector_repo.add(ids, embeddings, texts)
        vector_repo.delete(ids)
        results = vector_repo.search(query_embedding=[0.1, 0.2, 0.3], top_k=10)
        vec_ids = [r["id"] for r in results]
        assert "vec-to-delete" not in vec_ids

    def test_get_by_document_id_uses_metadata_filter(self, vector_repo):
        """按文档ID取 chunks：存储层 metadata 过滤，不构造零向量（回归：原 1024 维零向量 hack）"""
        ids = [f"doc-a-{i}" for i in range(3)] + [f"doc-b-{i}" for i in range(2)]
        embeddings = [[0.1, 0.2, 0.3]] * 5
        texts = ["text-a"] * 3 + ["text-b"] * 2
        metadatas = [{"document_id": "doc-a"}] * 3 + [{"document_id": "doc-b"}] * 2
        vector_repo.add(ids, embeddings, texts, metadatas)

        chunks_a = vector_repo.get_by_document_id("doc-a")
        assert len(chunks_a) == 3
        assert {c["id"] for c in chunks_a} == {"doc-a-0", "doc-a-1", "doc-a-2"}
        assert all(c["metadata"]["document_id"] == "doc-a" for c in chunks_a)
        assert chunks_a[0]["text"] == "text-a"

        chunks_b = vector_repo.get_by_document_id("doc-b")
        assert len(chunks_b) == 2
        assert vector_repo.get_by_document_id("doc-missing") == []

    def test_stats(self, vector_repo):
        """Test getting vector store stats"""
        stats = vector_repo.get_stats()
        assert "type" in stats
        assert "collection" in stats
