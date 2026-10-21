#!/usr/bin/env python3
"""
Vector Store Module

向量存储基础设施：抽象基类 + Chroma 实现。
后续新增向量数据库时，在本模块中扩展新的实现类。
"""

from abc import ABC, abstractmethod
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings
from pymilvus import CollectionSchema, DataType, FieldSchema, MilvusClient

from qingchuan_rag.core.exceptions import VectorStoreError
from qingchuan_rag.core.logger import logger
from qingchuan_rag.core.paths import resolve_service_path


class VectorStoreBase(ABC):
    """向量存储基类

    定义向量存储的标准接口
    """

    @abstractmethod
    def initialize(self) -> None:
        """初始化向量存储"""
        pass

    @abstractmethod
    def shutdown(self) -> None:
        """关闭向量存储"""
        pass

    @abstractmethod
    def add(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        """添加向量

        Args:
            ids: 向量ID列表
            embeddings: 向量列表
            documents: 原始文档文本列表
            metadatas: 元数据列表
        """
        pass

    @abstractmethod
    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        where: dict[str, Any] | None = None,
        include: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """搜索相似向量

        Args:
            query_embedding: 查询向量
            top_k: 返回数量
            where: 过滤条件
            include: 返回字段

        Returns:
            list[dict[str, Any]]: 搜索结果列表
        """
        pass

    @abstractmethod
    def delete(self, ids: list[str]) -> None:
        """删除向量

        Args:
            ids: 向量ID列表
        """
        pass

    @abstractmethod
    def delete_by_metadata(self, metadata_filter: dict[str, Any]) -> int:
        """按元数据等值条件删除向量（如 {"document_id": "doc_001"}）

        Args:
            metadata_filter: 元数据过滤条件（等值匹配）

        Returns:
            int: 删除的向量数量
        """
        pass

    @abstractmethod
    def get_count(self) -> int:
        """获取向量总数

        Returns:
            int: 向量数量
        """
        pass

    @abstractmethod
    def get_stats(self) -> dict[str, Any]:
        """获取统计信息

        Returns:
            dict[str, Any]: 统计信息
        """
        pass


class ChromaVectorStore(VectorStoreBase):
    """Chroma向量存储实现"""

    DISTANCE_MAP = {
        "cosine": "cosine",
        "euclidean": "l2",
        "dot": "ip",
    }

    def __init__(
        self,
        persist_directory: str = "./data/chroma",
        collection_name: str = "documents",
        distance_type: str = "cosine",
    ):
        # 相对路径锚定到服务根目录（apps/rag-service/data），避免随 CWD 漂移写入仓库根目录
        self.persist_directory = resolve_service_path(persist_directory)
        self.collection_name = collection_name
        self.distance_type = distance_type
        self._client: chromadb.PersistentClient | None = None
        self._collection = None
        self._initialized = False

    def initialize(self) -> None:
        """初始化Chroma客户端和集合"""
        if self._initialized:
            return

        try:
            self._client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=ChromaSettings(
                    anonymized_telemetry=False,
                    allow_reset=True,
                ),
            )

            distance_metric = self.DISTANCE_MAP.get(self.distance_type, "cosine")

            self._collection = self._client.get_or_create_collection(
                name=self.collection_name, metadata={"hnsw:space": distance_metric}
            )

            self._initialized = True
            logger.info(
                f"ChromaVectorStore initialized: collection={self.collection_name}, "
                f"distance={distance_metric}"
            )

        except Exception as e:
            logger.error(f"Failed to initialize ChromaVectorStore: {e}")
            raise VectorStoreError(f"Failed to initialize: {e}") from e

    def shutdown(self) -> None:
        """关闭Chroma客户端"""
        if self._initialized:
            self._client = None
            self._collection = None
            self._initialized = False
            logger.info("ChromaVectorStore shut down")

    def add(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        """添加向量到集合"""
        self._ensure_initialized()

        try:
            self._collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                # Chroma 要求 metadata 为非空 dict，None / 空 dict 都会报错
                metadatas=metadatas or [{"source": "x-qingchuan"} for _ in ids],
            )
            logger.debug(f"Added {len(ids)} vectors to collection")
        except Exception as e:
            logger.error(f"Failed to add vectors: {e}")
            raise VectorStoreError(f"Failed to add vectors: {e}") from e

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        where: dict[str, Any] | None = None,
        include: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """搜索相似向量"""
        self._ensure_initialized()

        if include is None:
            include = ["documents", "metadatas", "distances"]

        try:
            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where,
                include=include,
            )

            if not results or not results.get("ids"):
                return []

            formatted_results = []
            ids_list = results.get("ids", [[]])[0]
            documents_list = results.get("documents", [[]])[0]
            metadatas_list = results.get("metadatas", [[]])[0]
            distances_list = results.get("distances", [[]])[0]

            for i in range(len(ids_list)):
                formatted_results.append(
                    {
                        "id": ids_list[i],
                        "text": documents_list[i] if i < len(documents_list) else "",
                        "metadata": metadatas_list[i] if i < len(metadatas_list) else {},
                        "distance": distances_list[i] if i < len(distances_list) else 0.0,
                    }
                )

            return formatted_results

        except Exception as e:
            logger.error(f"Failed to search vectors: {e}")
            raise VectorStoreError(f"Failed to search: {e}") from e

    def delete(self, ids: list[str]) -> None:
        """删除向量"""
        self._ensure_initialized()

        try:
            self._collection.delete(ids=ids)
            logger.debug(f"Deleted {len(ids)} vectors from collection")
        except Exception as e:
            logger.error(f"Failed to delete vectors: {e}")
            raise VectorStoreError(f"Failed to delete vectors: {e}") from e

    def delete_by_metadata(self, metadata_filter: dict[str, Any]) -> int:
        """按元数据等值条件删除向量（Chroma where 子句）。"""
        self._ensure_initialized()
        if not metadata_filter:
            return 0
        try:
            # 先按条件查询得到命中 id 列表（Chroma delete 的 where 在部分版本不可靠，先查后删）
            results = self._collection.get(where=metadata_filter, include=[])
            ids_to_delete = results.get("ids", []) if results else []
            if ids_to_delete:
                self._collection.delete(ids=ids_to_delete)
            count = len(ids_to_delete)
            logger.debug(f"Deleted {count} vectors by metadata filter {metadata_filter}")
            return count
        except Exception as e:
            logger.error(f"Failed to delete vectors by metadata: {e}")
            raise VectorStoreError(f"Failed to delete vectors by metadata: {e}") from e

    def get_count(self) -> int:
        """获取向量总数"""
        self._ensure_initialized()

        try:
            return self._collection.count()
        except Exception as e:
            logger.error(f"获取向量总数失败: {e}")
            raise VectorStoreError(f"获取向量总数失败: {e}") from e

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        self._ensure_initialized()

        try:
            return {
                "type": "chroma",
                "collection": self.collection_name,
                "count": self._collection.count(),
                "persist_directory": self.persist_directory,
            }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"type": "chroma", "error": str(e)}

    def _ensure_initialized(self) -> None:
        """确保已初始化"""
        if not self._initialized:
            raise VectorStoreError("VectorStore not initialized. Call initialize() first.")


class MilvusVectorStore(VectorStoreBase):
    """Milvus 向量存储实现（本地 milvus-lite 文件模式 / 远程 Milvus 服务）。

    通过配置 uri 切换：
        - 本地文件模式（开发默认）：uri="./data/milvus.db"（依赖 milvus-lite）
        - 远程服务模式（生产）：uri="http://milvus:19530"（依赖 pymilvus，可选 token）

    与 Chroma 输出结构对齐：search 返回 {id, text, metadata, distance}，
    其中 distance 统一为"距离语义"（小=相似，与 Chroma 一致）：
    Milvus COSINE 度量返回的是余弦相似度（大=相似），此处转 1 - similarity。
    集合 schema：varchar 主键 id + float vector + 动态字段（text/document_id 等元数据随插随建）。
    """

    METRIC_MAP = {
        "cosine": "COSINE",
        "euclidean": "L2",
        "dot": "IP",
    }

    def __init__(
        self,
        uri: str = "./data/milvus.db",
        collection_name: str = "documents",
        metric_type: str = "cosine",
        dimension: int | None = None,
    ):
        # 本地文件相对路径锚定到服务根目录；远程地址（http://...）原样保留
        self._uri = resolve_service_path(uri)
        self.collection_name = collection_name
        self._metric_type = self.METRIC_MAP.get(metric_type.lower(), "COSINE")
        self._dimension = dimension
        self._client: MilvusClient | None = None
        self._initialized = False

    def initialize(self) -> None:
        """连接 Milvus（构造即连接），存在时复用集合，缺省时待 add 首向量建集。"""
        if self._initialized:
            return
        try:
            self._client = MilvusClient(uri=self._uri)
            if self._dimension and not self._client.has_collection(self.collection_name):
                self._create_collection(self._dimension)
            self._initialized = True
            logger.info(
                f"MilvusVectorStore initialized: uri={self._uri}, "
                f"collection={self.collection_name}, metric={self._metric_type}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize MilvusVectorStore: {e}")
            raise VectorStoreError(f"Failed to initialize Milvus: {e}") from e

    def shutdown(self) -> None:
        """关闭 Milvus 客户端"""
        if self._initialized and self._client is not None:
            try:
                self._client.close()
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Milvus close warning: {e}")
            self._client = None
            self._initialized = False
            logger.info("MilvusVectorStore shut down")

    def add(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        """添加向量到集合（集合不存在时按首个向量维度自动创建）。"""
        self._ensure_initialized()
        if not ids or not embeddings:
            return
        try:
            if not self._client.has_collection(self.collection_name):
                self._create_collection(len(embeddings[0]))
            rows = []
            for index, chunk_id in enumerate(ids):
                row: dict[str, Any] = {
                    "id": chunk_id,
                    "vector": embeddings[index],
                    "text": documents[index] if index < len(documents) else "",
                }
                meta = (metadatas or [{}])[index] if index < len(metadatas or []) else {}
                row.update(meta)
                rows.append(row)
            self._client.insert(self.collection_name, rows)
            logger.debug(f"Added {len(rows)} vectors to Milvus collection")
        except Exception as e:
            logger.error(f"Failed to add vectors to Milvus: {e}")
            raise VectorStoreError(f"Failed to add vectors to Milvus: {e}") from e

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        where: dict[str, Any] | None = None,
        include: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """搜索相似向量。

        where: 元数据过滤条件（dict，如 {"document_id": "doc_001"}），
        内部转换为 Milvus filter 表达式（等值匹配；值统一按字符串处理）。
        """
        self._ensure_initialized()
        if include is None:
            include = ["documents", "metadatas", "distances"]
        try:
            if not self._client.has_collection(self.collection_name):
                return []
            filter_expr = self._build_filter_expr(where)
            results = self._client.search(
                self.collection_name,
                data=[query_embedding],
                limit=top_k,
                filter=filter_expr or "",
                output_fields=["text"],
                search_params={"metric_type": self._metric_type},
            )
            formatted: list[dict[str, Any]] = []
            for hit in (results[0] if results else []):
                entity = hit.get("entity") or {}
                metadata = {k: v for k, v in entity.items() if k != "text"}
                distance = hit.get("distance", 0.0)
                if self._metric_type == "COSINE":
                    # Milvus COSINE 返回相似度（1.0=最相似）→ 转距离语义（0.0=最相似），与 Chroma 一致
                    similarity = max(0.0, min(1.0, float(distance)))
                    distance = 1.0 - similarity
                formatted.append(
                    {
                        "id": str(hit.get("id", "")),
                        "text": entity.get("text", ""),
                        "metadata": metadata,
                        "distance": distance,
                    }
                )
            return formatted
        except Exception as e:
            logger.error(f"Failed to search vectors in Milvus: {e}")
            raise VectorStoreError(f"Failed to search in Milvus: {e}") from e

    def delete(self, ids: list[str]) -> None:
        """按主键删除向量"""
        self._ensure_initialized()
        if not ids:
            return
        try:
            self._client.delete(self.collection_name, ids=ids)
            logger.debug(f"Deleted {len(ids)} vectors from Milvus collection")
        except Exception as e:
            logger.error(f"Failed to delete vectors in Milvus: {e}")
            raise VectorStoreError(f"Failed to delete vectors in Milvus: {e}") from e

    def delete_by_metadata(self, metadata_filter: dict[str, Any]) -> int:
        """按元数据等值条件删除向量（如 {"document_id": "doc_001"}）。"""
        self._ensure_initialized()
        try:
            if not self._client.has_collection(self.collection_name):
                return 0
            filter_expr = self._build_filter_expr(metadata_filter)
            if not filter_expr:
                return 0
            deleted = self._client.delete(self.collection_name, filter=filter_expr)
            count = len(deleted) if isinstance(deleted, list) else int(deleted or 0)
            logger.debug(f"Deleted {count} vectors by metadata filter {metadata_filter}")
            return count
        except Exception as e:
            logger.error(f"Failed to delete vectors by metadata in Milvus: {e}")
            raise VectorStoreError(f"Failed to delete vectors by metadata in Milvus: {e}") from e

    def get_count(self) -> int:
        """获取向量总数"""
        self._ensure_initialized()
        try:
            if not self._client.has_collection(self.collection_name):
                return 0
            stats = self._client.get_collection_stats(self.collection_name)
            return int(stats.get("row_count", 0) or 0)
        except Exception as e:
            logger.error(f"Failed to get Milvus row count: {e}")
            raise VectorStoreError(f"Failed to get Milvus row count: {e}") from e

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        self._ensure_initialized()
        try:
            return {
                "type": "milvus",
                "uri": self._uri,
                "collection": self.collection_name,
                "metric_type": self._metric_type,
                "count": self.get_count(),
            }
        except Exception as e:
            logger.error(f"Failed to get Milvus stats: {e}")
            return {"type": "milvus", "error": str(e)}

    def _create_collection(self, dimension: int) -> None:
        """创建集合（varchar 主键 + float vector + 动态字段承载元数据）。"""
        fields = [
            FieldSchema("id", DataType.VARCHAR, max_length=128, is_primary=True),
            FieldSchema("vector", DataType.FLOAT_VECTOR, dim=dimension),
        ]
        schema = CollectionSchema(fields, enable_dynamic_field=True)
        self._client.create_collection(
            collection_name=self.collection_name,
            schema=schema,
            metric_type=self._metric_type,
        )
        logger.info(
            f"Milvus collection created: {self.collection_name} dim={dimension} metric={self._metric_type}"
        )

    def _build_filter_expr(self, where: dict[str, Any] | None) -> str:
        """把 dict 过滤条件转换为 Milvus filter 表达式（仅支持等值，多条件 AND）。"""
        if not where:
            return ""
        clauses = []
        for key, value in where.items():
            if isinstance(value, str):
                # 转义内部引号，防 filter 注入
                escaped = value.replace("\\", "\\\\").replace('"', '\\"')
                clauses.append(f'{key} == "{escaped}"')
            elif isinstance(value, (int, float)):
                clauses.append(f"{key} == {value}")
            else:
                clauses.append(f'{key} == "{str(value)}"')
        return " and ".join(clauses)

    def _ensure_initialized(self) -> None:
        """确保已初始化"""
        if not self._initialized:
            raise VectorStoreError("VectorStore not initialized. Call initialize() first.")


__all__ = [
    "VectorStoreBase",
    "ChromaVectorStore",
    "MilvusVectorStore",
]
