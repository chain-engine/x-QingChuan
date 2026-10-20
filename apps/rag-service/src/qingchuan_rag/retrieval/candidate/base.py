"""
Candidate Retrieval Base Module

Stage 2 — 候选召回抽象基类
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseRetrievalProvider(ABC):
    """
    候选召回提供者基类

    所有候选召回算法提供者都需要继承此类。
    候选召回包括：向量检索（Vector Retrieval）、关键词检索（Keyword Retrieval / BM25）。
    """

    name: str = ""
    description: str = ""

    @property
    @abstractmethod
    def vector_store(self) -> Any:
        """获取关联的向量存储"""
        pass

    @property
    @abstractmethod
    def embedding_model(self) -> Any:
        """获取关联的 embedding 模型"""
        pass

    @abstractmethod
    def search(
        self,
        query: str | list[float],
        top_k: int = 10,
        **kwargs,
    ) -> list[dict[str, Any]]:
        """
        执行检索

        Args:
            query: 查询文本或查询向量
            top_k: 返回结果数量
            **kwargs: 额外参数（如 metadata_filter 等）

        Returns:
            list[dict[str, Any]]: 检索结果列表，每项包含 id、text、score、metadata
        """
        pass

    def get_config(self) -> dict[str, Any]:
        """获取当前配置"""
        return {
            "name": self.name,
            "description": self.description,
        }
