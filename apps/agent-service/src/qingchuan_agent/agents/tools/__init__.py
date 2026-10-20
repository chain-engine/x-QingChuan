"""工具注册中心初始化（晴川 x-QingChuan）。

骨架：注册占位检索工具 rag.retrieve（只读）。
TODO: 封装 packages/common 的 MCP 客户端，真正调用 rag-service。
"""

from __future__ import annotations

from qingchuan_agent.agents.tools.registry import ToolSpec, tool_registry
from qingchuan_agent.constants import ToolPermissionLevel


def _retrieve_placeholder(query: str, top_k: int = 5) -> list[dict[str, object]]:
    """占位检索：TODO 经 MCP 客户端调用 rag-service（HTTP + MCP 双服务）。"""
    return []


tool_registry.register(
    ToolSpec(
        name="rag.retrieve",
        description="语义检索人社 / 社保资料（占位，待接 rag-service）",
        func=_retrieve_placeholder,
        permission_level=ToolPermissionLevel.READ,
    )
)

__all__ = ["tool_registry"]
