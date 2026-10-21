#!/usr/bin/env python3
"""
Vector Repository Module

Vector store repository
"""

from typing import Any

from qingchuan_rag.constants import DistanceType
from qingchuan_rag.core.logger import logger
from qingchuan_rag.infras.vector import ChromaVectorStore, MilvusVectorStore
from qingchuan_rag.repositories.base_repository import BaseRepository
from qingchuan_rag.utils.similarity import SimilaritySearchEngine


class VectorRepository(BaseRepository):
    """向量仓库（按 store_type 选择 Chroma / Milvus 实现）"""

    def __init__(
        self,
        persist_directory: str = "./data/chroma",
        collection_name: str = "documents",
        distance_type: str = "cosine",
        store_type: str = "chroma",
        milvus_uri: str = "./data/milvus.db",
        dimension: int | None = None,
    ):
        if store_type == "milvus":
            self._store = MilvusVectorStore(
                uri=milvus_uri,
                collection_name=collection_name,
                metric_type=distance_type,
                dimension=dimension,
            )
        else:
            self._store = ChromaVectorStore(
                persist_directory=persist_directory,
                collection_name=collection_name,
                distance_type=distance_type,
            )
        self._distance_type = self._parse_distance_type(distance_type)
        self._similarity_engine = SimilaritySearchEngine(distance_type=self._distance_type)
        self._initialized = False

    def _parse_distance_type(self, distance_type: str) -> DistanceType:
        """解析距离类型字符串"""
        mapping = {
            "cosine": DistanceType.COSINE,
            "euclidean": DistanceType.EUCLIDEAN,
            "dot": DistanceType.DOT,
        }
        return mapping.get(distance_type.lower(), DistanceType.COSINE)

    def initialize(self) -> None:
        """初始化向量存储"""
        if self._initialized:
            return
        self._store.initialize()
        self._initialized = True
        logger.info("VectorRepository initialized")

    def shutdown(self) -> None:
        """关闭向量存储"""
        if self._initialized:
            self._store.shutdown()
            self._initialized = False
            logger.info("VectorRepository shut down")

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        return self._store.get_stats()

    def add(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        """添加向量"""
        self._ensure_initialized()
        self._store.add(ids, embeddings, documents, metadatas)

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """搜索向量

        Args:
            query_embedding: 查询向量，形状为 [embedding_dim]，如 BGE 模型输出 1024 维向量
            top_k: 返回的最相似结果数量，默认 5
            where: 元数据过滤条件，支持 Chroma 的 where 子句格式

        Returns:
            结果列表，每个元素包含:
                - id (str): 向量 ID
                - document (str): 关联的文本内容
                - metadata (dict): 元数据（如 document_id、chunk_index 等）
                - score (float): 相似度分数（0-1，1 表示完全相似）

        Examples:
            # 基础搜索
            results = repo.search(
                query_embedding=[0.1, 0.2, ...],  # 1024 维向量
                top_k=5
            )

            # 带过滤条件的搜索
            results = repo.search(
                query_embedding=[0.1, 0.2, ...],
                top_k=10,
                where={"document_id": "doc_001"}  # 只返回该文档的 chunks
            )

            # 处理返回结果
            for r in results:
                print(f"Score: {r['score']:.4f}, Doc: {r['document'][:50]}...")
        """
        self._ensure_initialized()
        results = self._store.search(
            query_embedding=query_embedding,
            top_k=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        # 转换结果格式，并使用 SimilaritySearchEngine 计算相似度
        for result in results:
            distance = result.pop("distance", 0.0)
            embedding = result.get("embedding")

            # 如果有原始向量，使用 SimilaritySearchEngine 计算准确相似度
            if embedding is not None and isinstance(embedding, (list, tuple)):
                result["score"] = self._similarity_engine.compute(
                    query_vector=query_embedding,
                    doc_vector=embedding,
                    distance_type=self._distance_type,
                )
            elif distance is not None:
                # fallback: 根据距离类型转换
                if self._distance_type == DistanceType.COSINE:
                    result["score"] = 1.0 / (1.0 + distance)
                elif self._distance_type == DistanceType.EUCLIDEAN:
                    result["score"] = 1.0 / (1.0 + distance)
                else:
                    result["score"] = distance
            else:
                result["score"] = 0.0

        return results

    def delete(self, ids: list[str]) -> None:
        """删除向量"""
        self._ensure_initialized()
        self._store.delete(ids)

    def delete_by_document_id(self, document_id: str) -> int:
        """根据文档ID删除向量"""
        self._ensure_initialized()
        return self._store.delete_by_metadata({"document_id": document_id})

    def get_by_document_id(self, document_id: str) -> list[dict[str, Any]]:
        """根据文档ID获取向量"""
        self._ensure_initialized()

        results = self._store.search(
            query_embedding=[0.0] * 1024,
            top_k=10000,
            where={"document_id": document_id},
        )

        return [r for r in results if r.get("metadata", {}).get("document_id") == document_id]

    def get_count(self) -> int:
        """获取向量总数"""
        self._ensure_initialized()
        return self._store.get_count()

    def _ensure_initialized(self) -> None:
        """确保已初始化"""
        if not self._initialized:
            raise RuntimeError("VectorRepository not initialized. Call initialize() first.")
