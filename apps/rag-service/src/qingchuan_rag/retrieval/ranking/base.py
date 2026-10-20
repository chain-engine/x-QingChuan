"""
Ranking Base Module

Stage 3 — 排序筛选抽象基类
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseRerankingProvider(ABC):
    """
    重排序提供者基类

    对候选文档进行重排序，改变文档的相对顺序。
    包括：MMR 多样性排序、RRF 融合排序、语义重排。
    """

    name: str = ""
    description: str = ""

    @abstractmethod
    def rerank(
        self,
        query: str | list[float],
        candidates: list[dict[str, Any]],
        **kwargs,
    ) -> list[dict[str, Any]]:
        """
        对候选文档进行重排序

        Args:
            query: 查询文本或查询向量
            candidates: 候选文档列表，每项包含 id、text、score、metadata 等
            **kwargs: 额外参数

        Returns:
            list[dict[str, Any]]: 排序后的文档列表
        """
        pass

    @property
    def provider_name(self) -> str:
        """提供者名称"""
        return self.name

    def get_config(self) -> dict[str, Any]:
        """获取当前配置"""
        return {
            "name": self.name,
            "description": self.description,
        }


class BaseFilterProvider(ABC):
    """
    过滤提供者基类

    对候选文档进行过滤，根据条件筛选文档。
    过滤操作不改变文档顺序，仅决定保留或移除。
    包括：分值阈值过滤、元数据过滤等。
    """

    name: str = ""
    description: str = ""

    @abstractmethod
    def filter(
        self,
        candidates: list[dict[str, Any]],
        **kwargs,
    ) -> list[dict[str, Any]]:
        """
        对候选文档进行过滤

        Args:
            candidates: 候选文档列表，每项包含 id、text、score、metadata 等
            **kwargs: 额外参数

        Returns:
            list[dict[str, Any]]: 过滤后的文档列表
        """
        pass

    @property
    def provider_name(self) -> str:
        """提供者名称"""
        return self.name

    def get_config(self) -> dict[str, Any]:
        """获取当前配置"""
        return {
            "name": self.name,
            "description": self.description,
        }
