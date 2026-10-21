#!/usr/bin/env python3
"""
Document Service Module

文档业务服务 - 编排文档索引和管理全流程
包含文档上传、索引、删除、查询等业务逻辑
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from qingchuan_rag.constants import DocStatus
from qingchuan_rag.core.exceptions import DocumentError
from qingchuan_rag.core.logger import logger
from qingchuan_rag.infras.chunking import get_chunking_provider
from qingchuan_rag.infras.embedding import BGEEmbeddingModel
from qingchuan_rag.repositories.bm25_repository import BM25Repository
from qingchuan_rag.repositories.document_repository import DocumentRepository
from qingchuan_rag.repositories.vector_repository import VectorRepository
from qingchuan_rag.services.audit_service import AuditService
from qingchuan_rag.services.base_service import BaseService


class DocumentService(BaseService):
    """文档业务服务 - 封装文档索引和管理流程"""

    entity_type = "document"

    def __init__(
        self,
        vector_repo: VectorRepository,
        doc_repo: DocumentRepository,
        bm25_repo: BM25Repository | None = None,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        chunking_provider: str = "langchain",
        chunking_strategy: str = "recursive",
        audit_service: AuditService | None = None,
    ):
        self._vector_repo = vector_repo
        self._doc_repo = doc_repo
        self._bm25_repo = bm25_repo
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._initialized = False
        self._embedding_model: BGEEmbeddingModel | None = None
        self._audit_service = audit_service
        self._chunking_provider = get_chunking_provider(
            provider_name=chunking_provider,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            strategy=chunking_strategy,
        )
        logger.info(
            f"DocumentService initialized with chunking provider: {chunking_provider}/{chunking_strategy}"
        )

    def initialize(self) -> None:
        """初始化服务"""
        self._vector_repo.initialize()
        self._doc_repo.initialize()
        if self._bm25_repo:
            self._bm25_repo.initialize()
        self._initialized = True
        logger.info("DocumentService initialized (embedding model will be loaded on first use)")

    def shutdown(self) -> None:
        """关闭服务"""
        if self._initialized:
            self._vector_repo.shutdown()
            self._doc_repo.shutdown()
            if self._bm25_repo:
                self._bm25_repo.shutdown()
            if self._embedding_model:
                self._embedding_model.shutdown()
            self._initialized = False
            logger.info("DocumentService shut down")

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        stats = {
            "type": "document",
            "chunk_size": self._chunk_size,
            "chunk_overlap": self._chunk_overlap,
            "vector_stats": self._vector_repo.get_stats(),
            "document_stats": self._doc_repo.get_stats(),
        }
        if self._bm25_repo:
            stats["bm25_stats"] = self._bm25_repo.get_stats()
        return stats

    def _get_embedding_model(self) -> BGEEmbeddingModel:
        """延迟获取 embedding model"""
        if self._embedding_model is None:
            logger.info("Loading embedding model on first use...")
            self._embedding_model = BGEEmbeddingModel()
        return self._embedding_model

    def _check_initialized(self) -> None:
        """检查服务是否已初始化"""
        if not self._initialized:
            raise RuntimeError("DocumentService not initialized. Call initialize() first.")

    def _audit(
        self,
        entity_id: str | None,
        action: str,
        operator: dict[str, Any] | None = None,
        before_data: dict[str, Any] | None = None,
        after_data: dict[str, Any] | None = None,
        remarks: str | None = None,
    ) -> None:
        """记录文档操作审计（审计失败不阻断业务，由 AuditService 内部兜底）。"""
        if self._audit_service is None:
            return
        self._audit_service.log_event(
            entity_type=self.entity_type,
            entity_id=entity_id,
            action=action,
            operator=operator,
            before_data=before_data,
            after_data=after_data,
            remarks=remarks,
        )

    def upload_document(
        self,
        text: str,
        file_name: str = "",
        file_type: str = "txt",
        file_size: int = 0,
        metadata: dict[str, Any] | None = None,
        operator: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """上传并索引文档

        Args:
            text: 文档文本内容
            file_name: 文件名
            file_type: 文件类型
            file_size: 文件大小
            metadata: 额外元数据

        Returns:
            索引结果
        """
        self._check_initialized()

        if metadata is None:
            metadata = {}

        document_id = str(uuid.uuid4())

        try:
            # 保存文档元数据（Json格式）
            logger.info(f"Indexing document {document_id}: saving metadata...")
            self._doc_repo.save(
                {
                    "document_id": document_id,
                    "file_name": file_name,
                    "file_type": file_type,
                    "file_size": file_size,
                    "status": DocStatus.PROCESSING.mark,
                    "created_at": datetime.now(UTC).isoformat(),
                    "updated_at": datetime.now(UTC).isoformat(),
                    "metadata": metadata,
                }
            )
            logger.info(f"Document {document_id} metadata saved")

            # 切分文本
            logger.info(f"Document {document_id}: splitting text...")
            chunks = self._chunking_provider.chunk_text_with_metadata(
                text=text,
                document_id=document_id,
                metadata=metadata,
            )
            logger.info(f"Document {document_id}: split into {len(chunks)} chunks")

            if not chunks:
                raise DocumentError(f"No chunks generated for document {document_id}")

            # 提取文本
            chunk_texts = [chunk.content for chunk in chunks]

            # 向量化
            logger.info(f"Document {document_id}: encoding {len(chunk_texts)} chunks...")
            embeddings = self._get_embedding_model().encode(chunk_texts, normalize=True)
            logger.info(f"Document {document_id}: encoded successfully")

            # 存储向量（构建稠密索引）
            ids = [chunk.chunk_id for chunk in chunks]
            metadatas = [
                {
                    "document_id": document_id,
                    "chunk_index": str(idx),
                    **chunk.metadata,
                }
                for idx, chunk in enumerate(chunks)
            ]
            self._vector_repo.add(ids, embeddings, chunk_texts, metadatas)

            # 存储文本和元数据（构建 BM25 稀疏索引）
            logger.info(f"Document {document_id}: building BM25 sparse index...")
            self._bm25_repo.add(ids, chunk_texts, metadatas)
            logger.info(f"Document {document_id}: BM25 index built")

            # 更新文档状态
            self._doc_repo.update(
                document_id,
                {
                    "status": DocStatus.COMPLETED.mark,
                    "chunk_count": len(chunks),
                    "updated_at": datetime.now(UTC).isoformat(),
                },
            )

            logger.info(f"Successfully indexed document {document_id}")

            # 业务审计：文档上传（成功路径记录，after 为索引结果摘要，不记原文）
            self._audit(
                entity_id=document_id,
                action="upload",
                operator=operator,
                after_data={
                    "file_name": file_name,
                    "file_type": file_type,
                    "file_size": file_size,
                    "chunk_count": len(chunks),
                    "status": DocStatus.COMPLETED.mark,
                },
                remarks=f"上传文档「{file_name}」",
            )

            return {
                "document_id": document_id,
                "status": "completed",
                "chunk_count": len(chunks),
            }

        except Exception as e:
            import traceback

            logger.error(f"Failed to index document {document_id}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            self._doc_repo.update(document_id, {"status": DocStatus.FAILED.mark})
            raise DocumentError(f"Failed to index document {document_id}: {e}") from e

    def delete_document(
        self,
        document_id: str,
        operator: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """删除文档

        Args:
            document_id: 文档ID
            operator: 操作人上下文（用于审计）

        Returns:
            删除结果
        """
        self._check_initialized()

        try:
            # 删除前快照（审计 before_data）
            before = self._doc_repo.load(document_id)
            before_data = None
            if before is not None:
                before_data = {
                    "file_name": before.get("file_name"),
                    "file_type": before.get("file_type"),
                    "file_size": before.get("file_size", 0),
                    "status": before.get("status"),
                    "chunk_count": before.get("chunk_count", 0),
                }

            vector_count = self._vector_repo.delete_by_document_id(document_id)
            if self._bm25_repo:
                self._bm25_repo.delete_by_document_id(document_id)
            self._doc_repo.delete(document_id)

            logger.info(f"Successfully deleted document {document_id} ({vector_count} vectors)")

            # 业务审计：文档删除
            self._audit(
                entity_id=document_id,
                action="delete",
                operator=operator,
                before_data=before_data,
                after_data={"vector_count": vector_count, "status": "deleted"},
                remarks=f"删除文档「{before_data.get('file_name') if before_data else document_id}」",
            )

            return {
                "document_id": document_id,
                "status": "deleted",
                "vector_count": vector_count,
            }

        except Exception as e:
            logger.error(f"Failed to delete document {document_id}: {e}")
            raise DocumentError(f"Failed to delete document {document_id}: {e}") from e

    def get_document(
        self, document_id: str, operator: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """获取文档详情

        Args:
            document_id: 文档ID
            operator: 操作人上下文（读审计用，由 api 层传入；系统内部调用可不传）

        Returns:
            文档详情
        """
        self._check_initialized()

        document = self._doc_repo.load(document_id)

        if document is None:
            return {
                "document_id": document_id,
                "status": "not_found",
                "message": "Document not found",
            }

        vectors = self._vector_repo.get_by_document_id(document_id)

        chunks = []
        for vec in vectors:
            text = vec.get("text", "")
            chunks.append(
                {
                    "chunk_id": vec.get("id"),
                    "text": text[:200] + "..." if len(text) > 200 else text,
                    "metadata": vec.get("metadata", {}),
                }
            )

        result = {
            "document_id": document.get("document_id"),
            "file_name": document.get("file_name"),
            "file_type": document.get("file_type"),
            "file_size": document.get("file_size", 0),
            "status": document.get("status"),
            "chunk_count": document.get("chunk_count", 0),
            "vector_count": len(vectors),
            "created_at": document.get("created_at"),
            "updated_at": document.get("updated_at"),
            "metadata": document.get("metadata", {}),
            "chunks": chunks,
        }
        # 业务审计：文档读取（after 记摘要，不记全文与大字段）
        self._audit(
            entity_id=document_id,
            action="get",
            operator=operator,
            after_data={
                "file_name": result["file_name"],
                "file_type": result["file_type"],
                "status": result["status"],
                "chunk_count": result["chunk_count"],
                "vector_count": result["vector_count"],
            },
            remarks=f"读取文档「{result['file_name']}」详情",
        )
        return result

    def get_document_status(
        self, document_id: str, operator: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """获取文档状态

        Args:
            document_id: 文档ID
            operator: 操作人上下文（读审计用，由 api 层传入；系统内部调用可不传）

        Returns:
            文档状态
        """
        self._check_initialized()

        document = self._doc_repo.load(document_id)

        if document is None:
            return {
                "document_id": document_id,
                "status": "not_found",
            }

        vectors = self._vector_repo.get_by_document_id(document_id)

        result = {
            "document_id": document.get("document_id"),
            "file_name": document.get("file_name"),
            "status": document.get("status"),
            "chunk_count": document.get("chunk_count", 0),
            "vector_count": len(vectors),
        }
        # 业务审计：文档状态读取
        self._audit(
            entity_id=document_id,
            action="get_status",
            operator=operator,
            after_data={
                "file_name": result["file_name"],
                "status": result["status"],
                "chunk_count": result["chunk_count"],
                "vector_count": result["vector_count"],
            },
            remarks=f"查询文档「{result['file_name']}」状态",
        )
        return result

    def list_documents(
        self,
        status: str | None = None,
        file_type: str | None = None,
        skip: int = 0,
        limit: int | None = None,
        operator: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """列出文档

        Args:
            status: 按状态筛选
            file_type: 按文件类型筛选
            skip: 跳过数量
            limit: 返回数量限制
            operator: 操作人上下文（读审计用，由 api 层传入；系统内部调用可不传）

        Returns:
            文档列表
        """
        self._check_initialized()

        if skip < 0:
            skip = 0
        if limit is not None and limit < 1:
            limit = None

        # 过滤与分页下推到存储层：内存只保留当前页窗口，不再全量加载后切片
        documents, total = self._doc_repo.list_page(
            skip=skip,
            limit=limit,
            status=status,
            file_type=file_type,
        )

        result = {
            "documents": documents,
            "total": total,
            "skip": skip,
            "limit": limit,
        }
        # 业务审计：文档列表读取（after 记筛选条件与总数，不记明细，避免大 payload）
        self._audit(
            entity_id=None,
            action="list",
            operator=operator,
            after_data={
                "status": status,
                "file_type": file_type,
                "skip": skip,
                "limit": limit,
                "total": total,
            },
            remarks="查询文档列表",
        )
        return result
