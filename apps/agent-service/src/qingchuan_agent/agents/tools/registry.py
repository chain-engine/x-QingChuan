#!/usr/bin/env python3
"""工具注册中心（晴川 x-QingChuan，对齐北辰形态）。

工具 = Agent 可调用的外部能力（如知识检索 / 数据查询 / 通知）。
权限模型（对齐 ToolPermissionLevel）：
    - read   只读：Agent 可直接调用
    - write  写：不注册给 Agent，由人工 / 外部执行器执行

调用约定：Agent 节点通过 tool_registry.invoke(name, **kwargs) 调用，
只读工具直接执行；写工具抛 ForbiddenError（不降级静默）。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from qingchuan_agent.constants import ToolPermissionLevel
from qingchuan_agent.core.exceptions import ForbiddenError
from qingchuan_agent.core.logger import logger


@dataclass
class ToolSpec:
    """工具规格。"""

    name: str
    description: str
    func: Callable[..., Any] = field(repr=False)
    permission_level: ToolPermissionLevel = ToolPermissionLevel.READ
    enabled: bool = True


class ToolRegistry:
    """工具注册表（应用级单例）。"""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            logger.warning(f"工具重复注册，覆盖旧定义：{spec.name}")
        self._tools[spec.name] = spec
        logger.info(f"工具注册成功：{spec.name}（{spec.permission_level}）")

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def invoke(self, name: str, **kwargs: Any) -> Any:
        """调用工具（仅支持只读工具，写工具由人工 / 外部执行器执行）。

        Args:
            name: 工具名（如 "rag.retrieve"）
            **kwargs: 工具函数的实际参数

        Returns:
            工具函数执行结果

        Raises:
            ValueError: 工具不存在或已停用
            ForbiddenError: 工具为写工具（WRITE），Agent 不允许直接调用
        """
        spec = self.get(name)
        if spec is None or not spec.enabled:
            raise ValueError(f"工具不存在或已停用：{name}")
        if spec.permission_level != ToolPermissionLevel.READ:
            raise ForbiddenError(
                f"工具 {spec.name} 为写工具（{spec.permission_level}），Agent 不允许直接调用"
            )
        logger.info(f"[Tool] invoke {name}")
        return spec.func(**kwargs)

    def list_tools(self) -> list[ToolSpec]:
        return list(self._tools.values())


tool_registry: ToolRegistry = ToolRegistry()

__all__ = ["ToolRegistry", "ToolSpec", "tool_registry"]
