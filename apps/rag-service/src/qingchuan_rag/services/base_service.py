#!/usr/bin/env python3
"""
Base Service Module

服务基类，定义业务逻辑层的基础接口
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseService(ABC):
    """服务基类"""

    @abstractmethod
    def initialize(self) -> None:
        """初始化服务"""
        pass

    @abstractmethod
    def shutdown(self) -> None:
        """关闭服务"""
        pass

    @abstractmethod
    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        pass
