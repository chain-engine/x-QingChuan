"""
Metadata Filter Engine Module

元数据过滤引擎

— 根据文档的元数据字段进行条件过滤
"""

from typing import Any

from qingchuan_rag.core.logger import logger


class MetadataFilterEngine:
    """
    元数据过滤器引擎

    根据文档的元数据字段进行条件过滤，支持多种操作符。

    使用方式：
        engine = MetadataFilterEngine()
        filtered = engine.apply(documents, {"source": "wiki", "year": {"$gte": 2020}})
    """

    def __init__(self, default_operator: str = "$eq"):
        """
        初始化元数据过滤器

        Args:
            default_operator: 默认操作符（精确匹配）
        """
        self._default_operator = default_operator

    @property
    def default_operator(self) -> str:
        """获取默认操作符"""
        return self._default_operator

    def apply(
        self,
        documents: list[dict[str, Any]],
        metadata_filter: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        根据元数据过滤文档

        Args:
            documents: 文档列表，每个文档包含 metadata 字段
            metadata_filter: 过滤条件

        Returns:
            list[dict[str, Any]]: 过滤后的文档列表
        """
        if not metadata_filter:
            return documents

        filtered = [
            doc for doc in documents if self._matches(doc.get("metadata", {}), metadata_filter)
        ]

        logger.debug(
            f"MetadataFilterEngine: filtered {len(documents)} -> {len(filtered)} documents"
        )
        return filtered

    def _matches(
        self,
        metadata: dict[str, Any],
        filter_condition: dict[str, Any],
    ) -> bool:
        """
        检查元数据是否匹配过滤条件

        Args:
            metadata: 文档元数据
            filter_condition: 过滤条件

        Returns:
            bool: 是否匹配
        """
        for key, value in filter_condition.items():
            if key not in metadata:
                return False

            if isinstance(value, dict):
                if not self._apply_operator(metadata[key], value):
                    return False
            else:
                if metadata[key] != value:
                    return False

        return True

    def _apply_operator(self, field_value: Any, condition: dict[str, Any]) -> bool:
        """
        应用操作符进行条件判断

        支持的操作符：
        - $eq: 精确相等
        - $ne: 不等于
        - $gt: 大于
        - $gte: 大于等于
        - $lt: 小于
        - $lte: 小于等于
        - $in: 包含在列表中
        - $nin: 不包含在列表中
        - $contains: 字符串包含
        - $startswith: 字符串开头
        - $endswith: 字符串结尾
        """
        for op, op_value in condition.items():
            if op == "$eq":
                if field_value != op_value:
                    return False
            elif op == "$ne":
                if field_value == op_value:
                    return False
            elif op == "$gt":
                if not (isinstance(field_value, (int, float)) and field_value > op_value):
                    return False
            elif op == "$gte":
                if not (isinstance(field_value, (int, float)) and field_value >= op_value):
                    return False
            elif op == "$lt":
                if not (isinstance(field_value, (int, float)) and field_value < op_value):
                    return False
            elif op == "$lte":
                if not (isinstance(field_value, (int, float)) and field_value <= op_value):
                    return False
            elif op == "$in":
                if field_value not in op_value:
                    return False
            elif op == "$nin":
                if field_value in op_value:
                    return False
            elif op == "$contains":
                if not isinstance(field_value, str):
                    return False
                if op_value not in field_value:
                    return False
            elif op == "$startswith":
                if not isinstance(field_value, str):
                    return False
                if not field_value.startswith(op_value):
                    return False
            elif op == "$endswith":
                if not isinstance(field_value, str):
                    return False
                if not field_value.endswith(op_value):
                    return False
            else:
                return False

        return True
