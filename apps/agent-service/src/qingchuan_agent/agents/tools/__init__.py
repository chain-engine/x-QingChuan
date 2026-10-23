"""工具注册中心初始化（晴川 x-QingChuan）。

工具 = Agent 可调用的外部能力；各工具定义按域拆分模块：
    - rag.py：rag-service 的 MCP 工具（retrieve_docs / rag_query）注册为只读工具

本包导入即完成工具注册（rag.py 在模块级执行 tool_registry.register）。
"""

from __future__ import annotations

from qingchuan_agent.agents.tools import rag as rag  # 导入即注册

__all__ = ["rag"]
