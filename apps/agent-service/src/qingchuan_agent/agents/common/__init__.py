"""公共编排能力（晴川 x-QingChuan，agents/common）。

各业务 Agent 子图共享的"骨架样板"，实现高内聚、低耦合：
    - 业务 Agent 只关心自己的节点语义（怎么干具体活）
    - 检索片段上下文组装 / payload 提取 / todo 占位 / LLM 调用
      这类通用横切逻辑统一收敛在此，避免每个 Agent 重复实现
"""

from qingchuan_agent.agents.common.context import build_context
from qingchuan_agent.agents.common.nodes import call_llm, todo_node
from qingchuan_agent.agents.common.payload import extract_query, get_int

__all__ = ["build_context", "call_llm", "extract_query", "get_int", "todo_node"]
