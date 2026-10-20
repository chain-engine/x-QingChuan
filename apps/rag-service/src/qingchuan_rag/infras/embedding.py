#!/usr/bin/env python3
"""
Embedding Module

嵌入模型基础设施：抽象基类 + BGE-M3 实现
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod

# 使用 HuggingFace 镜像加速下载
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

from sentence_transformers import SentenceTransformer

from qingchuan_rag.constants import (
    DEFAULT_EMBEDDING_BATCH_SIZE,
    DEFAULT_EMBEDDING_DEVICE,
    DEFAULT_EMBEDDING_MODEL,
)
from qingchuan_rag.core.exceptions import EmbeddingError
from qingchuan_rag.core.logger import logger


class EmbeddingModelBase(ABC):
    """嵌入模型基类

    定义嵌入模型的标准接口
    """

    @property
    @abstractmethod
    def dimension(self) -> int:
        """获取向量维度"""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """获取模型名称"""
        pass

    @abstractmethod
    def encode(self, texts: list[str], normalize: bool = True) -> list[list[float]]:
        """编码文本列表为向量

        Args:
            texts: 文本列表
            normalize: 是否归一化

        Returns:
            list[list[float]]: 向量列表
        """
        pass

    @abstractmethod
    def encode_single(self, text: str, normalize: bool = True) -> list[float]:
        """编码单个文本为向量

        Args:
            text: 文本
            normalize: 是否归一化

        Returns:
            list[float]: 向量
        """
        pass

    @abstractmethod
    def shutdown(self) -> None:
        """关闭模型"""
        pass


class BGEEmbeddingModel(EmbeddingModelBase):
    """BGE嵌入模型实现"""

    def __init__(
        self,
        model_name: str = DEFAULT_EMBEDDING_MODEL,
        device: str = DEFAULT_EMBEDDING_DEVICE,
        batch_size: int = DEFAULT_EMBEDDING_BATCH_SIZE,
    ) -> None:
        self._model_name = model_name
        self._device = device
        self._batch_size = batch_size
        self._model: SentenceTransformer | None = None
        self._dimension: int = 0

    @property
    def dimension(self) -> int:
        """获取向量维度"""
        if self._dimension == 0:
            self._ensure_loaded()
        return self._dimension

    @property
    def model_name(self) -> str:
        """获取模型名称"""
        return self._model_name

    def encode(self, texts: list[str], normalize: bool = True) -> list[list[float]]:
        """编码文本列表为向量

        将人类可读的文本转换为数值向量表示。

        Args:
            texts: 待编码的文本列表
                示例: ["今天天气很好", "今天下雨了"]
            normalize: 是否归一化向量（默认True）
                - True: 向量长度归一化为1，便于计算余弦相似度（推荐）
                - False: 保留原始向量长度

        Returns:
            二维浮点数列表，每个子列表是一个文本的向量

        Example:
            >>> model = BGEEmbeddingModel()
            >>> vectors = model.encode(["苹果", "香蕉"])
            >>> # 返回: [[0.1, -0.2, ...], [0.5, 0.1, ...]]
        """
        self._ensure_loaded()

        if not texts:
            return []

        try:
            embeddings = self._model.encode(
                texts,
                batch_size=self._batch_size,
                normalize_embeddings=normalize,
                show_progress_bar=False,
                convert_to_numpy=True,
            )
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"Failed to encode texts: {e}")
            raise EmbeddingError(f"Failed to encode texts: {e}") from e

    def encode_single(self, text: str, normalize: bool = True) -> list[float]:
        """编码单个文本为向量"""
        return self.encode([text], normalize=normalize)[0]

    def shutdown(self) -> None:
        """关闭模型"""
        if self._model is not None:
            del self._model
            self._model = None
            self._dimension = 0
            logger.info("BGEEmbeddingModel shut down")

    def _ensure_loaded(self) -> None:
        """确保模型已加载"""
        if self._model is None:
            try:
                logger.info(f"Loading embedding model: {self._model_name} on {self._device}")
                self._model = SentenceTransformer(self._model_name, device=self._device)
                self._dimension = self._model.get_embedding_dimension()
                logger.info(f"Loaded embedding model with dimension {self._dimension}")
            except Exception as e:
                logger.error(f"Failed to load embedding model: {e}")
                raise EmbeddingError(f"Failed to load model: {e}") from e


__all__ = [
    "EmbeddingModelBase",
    "BGEEmbeddingModel",
]
