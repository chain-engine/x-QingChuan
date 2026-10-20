"""
Vector Index Optimizer Module

向量索引优化工具

— 提供向量索引调优、内存估算等功能
"""

from dataclasses import dataclass
from typing import Any

from qingchuan_rag.core.logger import logger


@dataclass
class IndexConfig:
    """索引配置参数"""

    index_type: str
    params: dict[str, Any]


@dataclass
class MemoryEstimate:
    """内存估算结果"""

    index_type: str
    estimated_bytes: int
    estimated_mb: float
    estimated_gb: float
    dimension: int
    num_vectors: int


class VectorIndexOptimizer:
    """
    向量索引优化器

    提供向量索引参数优化、内存估算等功能，支持：
    - HNSW 参数调优
    - IVF 量化参数优化
    - 内存占用估算
    """

    @staticmethod
    def optimize_hnsw(
        ef_construction: int = 200,
        M: int = 16,
        ef_search: int | None = None,
    ) -> IndexConfig:
        """
        优化 HNSW 索引参数

        Args:
            ef_construction: 构建时的搜索范围，越大越精确但越慢（建议 100-400）
            M: 每个节点的连接数，越大越精确但内存占用越高（建议 8-64）
            ef_search: 查询时的搜索范围（默认等于 ef_construction）

        Returns:
            IndexConfig: 优化后的索引配置
        """
        effective_ef_search = ef_search if ef_search is not None else ef_construction

        params = {
            "ef_construction": ef_construction,
            "M": M,
            "ef_search": effective_ef_search,
        }

        logger.debug(f"VectorIndexOptimizer: HNSW config = {params}")
        return IndexConfig(index_type="hnsw", params=params)

    @staticmethod
    def optimize_ivf(
        nlist: int = 100,
        nprobe: int = 10,
        nlist_auto: bool = False,
        n_vectors: int | None = None,
    ) -> IndexConfig:
        """
        优化 IVF（倒排文件）索引参数

        Args:
            nlist: 聚类中心数量（建议 sqrt(n_vectors) 到 4*sqrt(n_vectors)）
            nprobe: 查询时搜索的聚类数量（越多越精确但越慢）
            nlist_auto: 是否自动计算 nlist
            n_vectors: 向量总数（用于自动计算）

        Returns:
            IndexConfig: 优化后的索引配置
        """
        if nlist_auto and n_vectors is not None:
            import math

            nlist = max(1, int(4 * math.sqrt(n_vectors)))

        params = {
            "nlist": nlist,
            "nprobe": nprobe,
        }

        logger.debug(f"VectorIndexOptimizer: IVF config = {params}")
        return IndexConfig(index_type="ivf", params=params)

    @staticmethod
    def optimize_quantization(
        n_bits: int = 8,
        nlist: int = 256,
        nprobe: int = 16,
    ) -> IndexConfig:
        """
        优化 PQ/SQ 量化参数

        Args:
            n_bits: 每个向量的压缩位数（8, 16, 32）
            nlist: PQ 聚类中心数量
            nprobe: 查询时的聚类搜索数量

        Returns:
            IndexConfig: 优化后的量化配置
        """
        params = {
            "n_bits": n_bits,
            "nlist": nlist,
            "nprobe": nprobe,
        }

        logger.debug(f"VectorIndexOptimizer: Quantization config = {params}")
        return IndexConfig(index_type="pq", params=params)

    @staticmethod
    def estimate_memory(
        num_vectors: int,
        dimension: int,
        index_type: str = "flat",
        **kwargs,
    ) -> MemoryEstimate:
        """
        估算向量索引的内存占用

        Args:
            num_vectors: 向量总数
            dimension: 向量维度
            index_type: 索引类型（flat, hnsw, ivf, pq）
            **kwargs: 额外参数（HNSW 需 ef_construction, M; IVF 需 nlist）

        Returns:
            MemoryEstimate: 内存估算结果
        """
        bytes_per_float = 4

        if index_type == "flat":
            bytes_per_vector = dimension * bytes_per_float
            total_bytes = num_vectors * bytes_per_vector

        elif index_type == "hnsw":
            M = kwargs.get("M", 16)
            ef_construction = kwargs.get("ef_construction", 200)
            base_memory = num_vectors * dimension * bytes_per_float
            graph_memory = num_vectors * (M * 2 + 1) * 8
            layer_memory = num_vectors * (ef_construction / 10) * 8
            total_bytes = int(base_memory + graph_memory + layer_memory)

        elif index_type == "ivf":
            nlist = kwargs.get("nlist", max(1, int(4 * (num_vectors**0.5))))
            bytes_per_vector = dimension * bytes_per_float
            center_vectors = nlist * dimension * bytes_per_float
            vector_memory = num_vectors * bytes_per_vector
            total_bytes = int(center_vectors + vector_memory)

        elif index_type == "pq":
            n_bits = kwargs.get("n_bits", 8)
            n_subvectors = kwargs.get("n_subvectors", dimension // 4)
            code_per_vector = (dimension * n_bits) // 8
            code_memory = num_vectors * code_per_vector
            center_memory = (n_subvectors * 256 * n_bits) // 8
            total_bytes = int(code_memory + center_memory)

        else:
            bytes_per_vector = dimension * bytes_per_float
            total_bytes = num_vectors * bytes_per_vector

        estimated_mb = total_bytes / (1024 * 1024)
        estimated_gb = total_bytes / (1024 * 1024 * 1024)

        logger.debug(
            f"VectorIndexOptimizer: Memory estimate for {num_vectors} vectors "
            f"({dimension}d, {index_type}): {estimated_mb:.2f} MB"
        )

        return MemoryEstimate(
            index_type=index_type,
            estimated_bytes=total_bytes,
            estimated_mb=estimated_mb,
            estimated_gb=estimated_gb,
            dimension=dimension,
            num_vectors=num_vectors,
        )

    @staticmethod
    def recommend_index_type(
        num_vectors: int,
        dimension: int,
        recall_target: float = 0.95,
        memory_limit_mb: float = 1024,
    ) -> str:
        """
        根据数据规模和资源限制推荐索引类型

        Args:
            num_vectors: 向量总数
            dimension: 向量维度
            recall_target: 召回率目标（0-1）
            memory_limit_mb: 内存限制（MB）

        Returns:
            str: 推荐的索引类型
        """
        flat_memory = VectorIndexOptimizer.estimate_memory(num_vectors, dimension, "flat")

        if flat_memory.estimated_mb <= memory_limit_mb:
            logger.info(f"Recommend 'flat' index: {flat_memory.estimated_mb:.2f} MB")
            return "flat"

        if recall_target >= 0.90:
            hnsw_memory = VectorIndexOptimizer.estimate_memory(
                num_vectors, dimension, "hnsw", M=16, ef_construction=200
            )
            if hnsw_memory.estimated_mb <= memory_limit_mb:
                logger.info(f"Recommend 'hnsw' index: {hnsw_memory.estimated_mb:.2f} MB")
                return "hnsw"

        pq_memory = VectorIndexOptimizer.estimate_memory(num_vectors, dimension, "pq", n_bits=8)
        if pq_memory.estimated_mb <= memory_limit_mb:
            logger.info(f"Recommend 'pq' index: {pq_memory.estimated_mb:.2f} MB")
            return "pq"

        logger.warning(f"No suitable index type found within {memory_limit_mb} MB limit")
        return "flat"
