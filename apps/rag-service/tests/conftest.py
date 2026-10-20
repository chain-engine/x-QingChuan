#!/usr/bin/env python3
"""
Pytest Configuration

定义测试夹具和配置
"""

import asyncio
import shutil
import tempfile
from pathlib import Path

import pytest

from qingchuan_rag.rag.augmentation import Augmentation
from qingchuan_rag.rag.generation import LLMGeneration
from qingchuan_rag.rag.pipeline import RAGPipeline
from qingchuan_rag.rag.retrieval import Retrieval
from qingchuan_rag.repositories.document_repository import DocumentRepository
from qingchuan_rag.repositories.vector_repository import VectorRepository
from qingchuan_rag.services.document_service import DocumentService


@pytest.fixture(scope="session", autouse=True)
def _qingchuan_session_env(tmp_path_factory):
    """测试会话级：初始化业务数据库（临时 SQLite，审计 / 同步任务状态表）。"""
    from qingchuan_rag.core.config import settings
    from qingchuan_rag.infras.database import init_database

    tmp = tmp_path_factory.mktemp("qingchuan_session")
    # Provider 架构下 db_url 从 settings 读取，测试指向临时 SQLite
    settings.database.db_url = f"sqlite:///{tmp}/qingchuan.db"
    init_database()
    yield


class _StubRAGService:
    """测试用 RAG 服务桩（避免加载真实 embedding 模型）。"""

    def initialize(self) -> None:
        pass

    def shutdown(self) -> None:
        pass

    def retrieve(self, **kwargs) -> list:
        return []

    async def query(self, **kwargs) -> dict:
        return {"answer": "stub", "documents": []}

    def encode(self, texts: list[str], normalize: bool = True, **kwargs) -> list:
        return [[0.0] * 8 for _ in texts]

    def get_embedding_stats(self) -> dict:
        return {"dimension": 8, "model": "stub"}

    def get_stats(self, operator=None) -> dict:
        return {"vector_count": 0}


class _StubDocumentService:
    """测试用文档服务桩。"""

    def initialize(self) -> None:
        pass

    def shutdown(self) -> None:
        pass

    def list_documents(self, status=None, file_type=None, skip=0, limit=20, operator=None) -> dict:
        return {"documents": [], "total": 0}

    def get_document(self, document_id: str, operator=None) -> dict:
        return {"status": "not_found"}

    def get_document_status(self, document_id: str, operator=None) -> dict:
        return {"status": "not_found"}

    def delete_document(self, document_id: str, operator: dict | None = None) -> dict:
        from qingchuan_rag.core.exceptions import DocumentError

        raise DocumentError(message=f"文档不存在: {document_id}")

    def upload_document(self, **kwargs) -> dict:
        return {"document_id": "stub-doc", "status": "completed", "chunk_count": 0}


@pytest.fixture(scope="session", autouse=True)
def _stub_services():
    """为 src.main.app 注入轻量服务桩，使 tests/api 可在不加载模型下运行。"""
    from qingchuan_rag.main import app

    if not hasattr(app.state, "rag_service"):
        app.state.rag_service = _StubRAGService()
    if not hasattr(app.state, "document_service"):
        app.state.document_service = _StubDocumentService()
    yield


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir():
    """临时目录夹具"""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def document_repository(temp_dir):
    """文档仓库测试夹具"""
    repo = DocumentRepository(storage_path=str(Path(temp_dir) / "documents"))
    repo.initialize()
    yield repo
    repo.shutdown()


@pytest.fixture
def vector_repository(temp_dir):
    """向量仓库测试夹具"""
    repo = VectorRepository(
        collection_name="test_collection",
        persist_directory=str(Path(temp_dir) / "chroma"),
    )
    repo.initialize()
    yield repo
    repo.shutdown()


@pytest.fixture
def document_service(document_repository, vector_repository):
    """文档服务测试夹具"""
    service = DocumentService(
        vector_repo=vector_repository,
        doc_repo=document_repository,
        chunk_size=100,
        chunk_overlap=10,
        chunking_provider="langchain",
        chunking_strategy="recursive",
    )
    service.initialize()
    yield service
    service.shutdown()


@pytest.fixture
def retrieval(vector_repository):
    """检索组件测试夹具"""
    ret = Retrieval(
        vector_repo=vector_repository,
        default_top_k=5,
        default_threshold=0.7,
    )
    ret.initialize()
    yield ret
    ret.shutdown()


@pytest.fixture
def augmentation():
    """增强组件测试夹具"""
    aug = Augmentation()
    aug.initialize()
    yield aug
    aug.shutdown()


@pytest.fixture
def generation():
    """生成组件测试夹具"""
    gen = LLMGeneration(
        default_provider="mock",
        default_model="mock-model",
    )
    gen.initialize()
    yield gen
    gen.shutdown()


@pytest.fixture
def rag_pipeline(retrieval, augmentation, generation):
    """RAG 流水线测试夹具"""
    pipeline = RAGPipeline(
        retrieval=retrieval,
        augmentation=augmentation,
        generation=generation,
    )
    pipeline.initialize()
    yield pipeline
    pipeline.shutdown()


@pytest.fixture
def text_splitter():
    """文本切分器测试夹具（chunking 模块 langchain provider）"""
    from qingchuan_rag.infras.chunking import get_chunking_provider

    return get_chunking_provider(
        provider_name="langchain",
        chunk_size=100,
        chunk_overlap=10,
        strategy="recursive",
    )


@pytest.fixture
def sample_text():
    """示例文本"""
    return """
    Python是一种高级编程语言，由Guido van Rossum于1991年首次发布。
    Python的设计哲学强调代码的可读性和简洁的语法。
    相比于C++或Java，Python让开发者能够用更少的代码表达概念。

    Python支持多种编程范式，包括面向对象、命令式、函数式和过程式编程。
    它拥有一个庞大而全面的标准库。
    """


@pytest.fixture
def sample_documents():
    """示例文档列表"""
    return [
        {
            "text": "Python是一种高级编程语言，由Guido van Rossum于1991年首次发布。",
            "metadata": {"topic": "python", "year": 1991},
        },
        {
            "text": "JavaScript是一种脚本语言，主要用于Web开发。",
            "metadata": {"topic": "javascript", "year": 1995},
        },
        {
            "text": "Rust是一种系统编程语言，注重安全性和性能。",
            "metadata": {"topic": "rust", "year": 2010},
        },
    ]
