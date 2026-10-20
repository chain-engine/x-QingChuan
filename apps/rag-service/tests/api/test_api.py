"""
Health Check API Tests
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client"""
    from qingchuan_rag.main import app

    return TestClient(app)


class TestHealthEndpoints:
    """Test health check endpoints"""

    def test_health_check(self, client):
        """Test basic health check"""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "data" in data

    def test_health_with_details(self, client):
        """Test health check with details"""
        response = client.get("/api/v1/health?detail=true")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200


class TestRAGEndpoints:
    """Test RAG API endpoints"""

    def test_retrieve_endpoint_validation(self, client):
        """Test retrieve endpoint input validation"""
        response = client.post("/api/v1/rag/retrieve", json={"query": ""})
        # 项目将 RequestValidationError 统一转为 400（见 main.py validation_exception_handler）
        assert response.status_code == 400

    def test_retrieve_endpoint_empty_db(self, client):
        """Test retrieve with empty database"""
        response = client.post("/api/v1/rag/retrieve", json={"query": "test query", "top_k": 5})
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["data"]["total"] == 0

    def test_stats_endpoint(self, client):
        """Test stats endpoint"""
        response = client.get("/api/v1/rag/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "data" in data


class TestDocumentEndpoints:
    """Test document management endpoints"""

    def test_list_documents_empty(self, client):
        """Test listing documents when empty"""
        response = client.get("/api/v1/documents")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["data"]["total"] == 0

    def test_list_documents_pagination(self, client):
        """Test document list pagination parameters"""
        response = client.get("/api/v1/documents?page=1&page_size=10")
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["page"] == 1
        assert data["data"]["page_size"] == 10

    def test_list_documents_page_size_limit(self, client):
        """Test document list page size limit"""
        response = client.get("/api/v1/documents?page_size=200")
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["page_size"] == 100

    def test_get_document_not_found(self, client):
        """Test getting non-existent document"""
        response = client.get("/api/v1/documents/nonexistent-id")
        assert response.status_code == 404

    def test_delete_document_not_found(self, client):
        """Test deleting non-existent document"""
        response = client.delete("/api/v1/documents/nonexistent-id")
        assert response.status_code == 400


class TestInputValidation:
    """Test input validation"""

    def test_invalid_page_parameter(self, client):
        """Test invalid page parameter"""
        response = client.get("/api/v1/documents?page=0")
        assert response.status_code == 200

    def test_invalid_page_size_parameter(self, client):
        """Test invalid page_size parameter"""
        response = client.get("/api/v1/documents?page_size=-1")
        assert response.status_code == 200
