#!/usr/bin/env python3
"""
RAG Service Module

RAG业务服务 - 编排检索、增强、生成全流程
"""

from typing import Any

from qingchuan_rag.core.logger import logger
from qingchuan_rag.rag.pipeline import RAGPipeline
from qingchuan_rag.services.audit_service import AuditService


class RAGService:
    """RAG业务服务 - 封装RAG完整流程"""

    def __init__(
        self,
        pipeline: RAGPipeline,
        audit_service: AuditService | None = None,
    ):
        self.pipeline = pipeline
        self._audit_service = audit_service

    def _audit(
        self,
        action: str,
        operator: dict[str, Any] | None = None,
        after_data: dict[str, Any] | None = None,
    ) -> None:
        """记录 RAG 调用审计（entity_type 按操作区分；审计失败不阻断业务）。"""
        if self._audit_service is None:
            return
        self._audit_service.log_event(
            entity_type=f"rag_{action}",
            entity_id=None,
            action=action,
            operator=operator,
            after_data=after_data,
            remarks=f"RAG {action} 调用",
        )

    def initialize(self) -> None:
        """初始化"""
        self.pipeline.initialize()
        logger.info("RAGService initialized")

    def shutdown(self) -> None:
        """关闭"""
        self.pipeline.shutdown()
        logger.info("RAGService shut down")

    def get_stats(self, operator: dict[str, Any] | None = None) -> dict[str, Any]:
        """获取统计信息

        Args:
            operator: 操作人上下文（读审计用，由 api 层传入；系统内部调用可不传）

        Returns:
            统计信息
        """
        stats = self.pipeline.get_stats()
        # 业务审计：统计读取（after 记标量摘要，避免大 payload）
        self._audit(
            action="stats",
            operator=operator,
            after_data={
                "vector_count": stats.get("vector_count"),
                "document_count": stats.get("document_count"),
            },
        )
        return stats

    async def query(
        self,
        query: str,
        top_k: int = 5,
        similarity_threshold: float = 0.7,
        use_mmr: bool = False,
        mmr_lambda: float = 0.5,
        rrf_k: int | None = None,
        metadata_filter: dict[str, Any] | None = None,
        provider: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        operator: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """RAG查询 - 完整流程

        Args:
            query: 用户查询
            top_k: 检索数量
            similarity_threshold: 相似度阈值
            use_mmr: 是否使用MMR重排序
            mmr_lambda: MMR参数
            rrf_k: RRF 融合常数（None=装配默认）
            metadata_filter: 元数据过滤条件
            provider: LLM提供商
            temperature: 温度参数
            max_tokens: 最大token数
            operator: 操作人上下文（用于审计）

        Returns:
            RAG查询结果
        """
        result = await self.pipeline.query(
            query=query,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
            use_mmr=use_mmr,
            mmr_lambda=mmr_lambda,
            rrf_k=rrf_k,
            metadata_filter=metadata_filter,
            provider=provider,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        # 业务审计：记录查询摘要（不记答案全文，避免大字段与敏感内容落库）
        self._audit(
            action="query",
            operator=operator,
            after_data={
                "query": query,
                "top_k": top_k,
                "doc_count": len(result.get("retrieved_docs") or []),
                "provider": result.get("provider"),
                "model": result.get("model"),
            },
        )
        return result

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        similarity_threshold: float = 0.7,
        use_mmr: bool = False,
        mmr_lambda: float = 0.5,
        rrf_k: int | None = None,
        metadata_filter: dict[str, Any] | None = None,
        operator: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """仅检索 - 不进行生成

        Args:
            query: 用户查询的文本
            top_k: 检索数量
            similarity_threshold: 相似度阈值
            use_mmr: 是否使用MMR重排序
            mmr_lambda: MMR参数
            rrf_k: RRF 融合常数（None=装配默认）
            metadata_filter: 元数据过滤条件
            operator: 操作人上下文（用于审计）

        Returns:
            检索到的文档列表
        """
        documents = self.pipeline.retrieval.retrieve(
            query=query,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
            use_mmr=use_mmr,
            mmr_lambda=mmr_lambda,
            rrf_k=rrf_k,
            metadata_filter=metadata_filter,
        )
        # 业务审计：记录检索摘要（不记片段原文）
        self._audit(
            action="retrieve",
            operator=operator,
            after_data={"query": query, "top_k": top_k, "doc_count": len(documents)},
        )
        return documents

    def get_vector_count(self) -> int:
        """获取向量总数"""
        return self.pipeline.retrieval.get_vector_count()

    def encode(self, texts: list[str], normalize: bool = True) -> list[list[float]]:
        """将文本转换为向量

        Args:
            texts: 文本列表
            normalize: 是否归一化

        Returns:
            向量列表
        """
        return self.pipeline.retrieval.encode(texts, normalize=normalize)

    def get_embedding_stats(self, operator: dict[str, Any] | None = None) -> dict[str, Any]:
        """获取嵌入模型统计信息

        Args:
            operator: 操作人上下文（读审计用，由 api 层传入；系统内部调用可不传）

        Returns:
            嵌入模型统计信息
        """
        stats = self.pipeline.retrieval.get_embedding_stats()
        # 业务审计：向量化能力调用（被 /rag/embed 开放接口调用时记录）
        self._audit(
            action="embed_stats",
            operator=operator,
            after_data={
                "dimension": stats.get("dimension"),
                "model": stats.get("model"),
            },
        )
        return stats
