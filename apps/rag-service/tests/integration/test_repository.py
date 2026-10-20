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
        repo = DocumentRepository(storage_path=temp_storage)
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
        assert loaded["content"] == "Test content"

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
        assert loaded["content"] == "Updated"
        assert loaded["version"] == 2

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

    def test_stats(self, vector_repo):
        """Test getting vector store stats"""
        stats = vector_repo.get_stats()
        assert "type" in stats
        assert "collection" in stats
