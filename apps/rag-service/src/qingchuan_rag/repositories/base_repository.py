#!/usr/bin/env python3
"""
Base Repository Module

仓库基类，定义数据访问层的基础接口
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseRepository(ABC):
    """仓库基类"""

    @abstractmethod
    def initialize(self) -> None:
        """初始化仓库"""
        pass

    @abstractmethod
    def shutdown(self) -> None:
        """关闭仓库"""
        pass

    @abstractmethod
    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        pass
