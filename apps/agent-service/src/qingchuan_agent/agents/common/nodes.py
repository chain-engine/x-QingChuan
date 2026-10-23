"""通用编排节点（晴川 x-QingChuan，agents/common）。

骨架阶段的公共节点样板：
    - todo_node(name)：未实现步骤的占位节点。返回 SUCCESS + result.todo 标记，
      保证骨架阶段整条编排链路可跑通（与 MockLLM 策略一致）；
      接入真实业务时把图里该节点替换为真实节点函数即可，图结构不变。
    - call_llm(messages)：统一 LLM 对话补全入口（真实 key 走 LangChain，
      未配置走 Mock 并标注；异常上抛由业务节点按状态机处理）。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from qingchuan_agent.agents.state import AgentTaskState
from qingchuan_agent.constants import TaskStatus
from qingchuan_agent.core.logger import logger
from qingchuan_agent.infras.llm import get_llm_provider


def todo_node(name: str) -> Callable[[AgentTaskState], dict[str, Any]]:
    """构造一个 todo 占位节点函数（骨架阶段未实现步骤）。

    Args:
        name: 步骤名（用于日志与 result.todo 标记）

    Returns:
        节点函数：写入 SUCCESS + result（todo 标记），保证链路可跑通。
    """

    def _node(state: AgentTaskState) -> dict[str, Any]:
        logger.info(f"[{name}] 骨架占位：步骤未实现（后续接入真实业务）")
        return {
            "status": TaskStatus.SUCCESS.mark,
            "result": {
                "todo": name,
                "message": f"【骨架占位】{name} 尚未实现，待接入真实业务逻辑。",
            },
        }

    return _node


def call_llm(messages: list[dict[str, Any]], **kwargs: Any) -> str:
    """统一 LLM 对话补全：真实 key 走 LangChain 实现，未配置走 Mock 并标注。

    Args:
        messages: OpenAI 风格消息列表 [{role, content}, ...]
        **kwargs: 透传 LLM 调用参数

    Returns:
        生成文本。LLM 调用失败抛异常，由业务节点按状态机归一。

    Raises:
        Exception: 底层 LLM 调用异常（不在此吞掉，交给节点状态机）。
    """
    provider = get_llm_provider()
    logger.info(f"[common.call_llm] 发送 {len(messages)} 条消息")
    return provider.chat(messages, **kwargs)


__all__ = ["call_llm", "todo_node"]
