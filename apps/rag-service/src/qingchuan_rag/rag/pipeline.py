"""
RAG Pipeline Module

RAG管道 — 编排检索、增强、生成三个环节
"""

from typing import Any

from qingchuan_rag.core.logger import logger
from qingchuan_rag.rag.augmentation import Augmentation
from qingchuan_rag.rag.generation import LLMGeneration
from qingchuan_rag.rag.retrieval import Retrieval


class RAGPipeline:
    """RAG管道 - 编排"检索->增强->生成"全流程"""

    def __init__(
        self,
        retrieval: Retrieval,
        augmentation: Augmentation,
        generation: LLMGeneration,
    ):
        self.retrieval = retrieval
        self.augmentation = augmentation
        self.generation = generation

    def initialize(self) -> None:
        """初始化所有组件"""
        self.retrieval.initialize()
        self.augmentation.initialize()
        self.generation.initialize()
        logger.info("RAGPipeline initialized")

    def shutdown(self) -> None:
        """关闭所有组件"""
        self.retrieval.shutdown()
        self.augmentation.shutdown()
        self.generation.shutdown()
        logger.info("RAGPipeline shut down")

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        vector_count = self.retrieval.get_vector_count()
        return {
            "retrieval": self.retrieval.get_stats(),
            "vector_count": vector_count,
            "augmentation": {
                "type": "augmentation",
                "context_length": self.augmentation._max_context_length,
            },
            "generation": self.generation.get_stats(),
        }

    async def query(
        self,
        query: str,
        top_k: int = 5,
        similarity_threshold: float = 0.7,
        use_mmr: bool = False,
        mmr_lambda: float = 0.5,
        metadata_filter: dict[str, Any] | None = None,
        provider: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """执行RAG查询

        Args:
            query: 用户查询
            top_k: 检索数量
            similarity_threshold: 相似度阈值
            use_mmr: 是否使用MMR重排序
            mmr_lambda: MMR参数
            metadata_filter: 元数据过滤条件
            provider: LLM提供商
            temperature: 温度参数
            max_tokens: 最大token数

        Returns:
            RAG查询结果
        """
        # 1. 检索
        retrieved_docs = self.retrieval.retrieve(
            query=query,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
            use_mmr=use_mmr,
            mmr_lambda=mmr_lambda,
            metadata_filter=metadata_filter,
        )

        if not retrieved_docs:
            return {
                "query": query,
                "answer": "抱歉，没有找到相关文档内容。",
                "retrieved_docs": [],
                "provider": "none",
                "model": "none",
                "tokens_used": None,
            }

        # 2. 增强
        augmented = self.augmentation.augment(
            query=query,
            retrieved_docs=retrieved_docs,
        )

        # 3. 生成
        generation_result = await self.generation.generate(
            prompt=augmented["full_prompt"],
            provider=provider,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # 4. 组装返回
        return {
            "query": query,
            "answer": generation_result["text"],
            "retrieved_docs": retrieved_docs,
            "provider": generation_result["provider"],
            "model": generation_result["model"],
            "tokens_used": generation_result["tokens_used"],
            "augmentation_stats": {
                "context_count": augmented["context_count"],
                "context_length": augmented["context_length"],
            },
        }
