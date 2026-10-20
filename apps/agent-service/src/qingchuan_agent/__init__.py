"""Agent 编排层（晴川 x-QingChuan，LangGraph + LangChain 标准实现，对齐北辰形态）。

顶层包仅做编排层符号重导出；编排层实现在 agents/ 子包：
    agents/base.py          BaseAgent 抽象基类（子图构建契约）
    agents/state.py         共享状态 TypedDict（顶层编排 + 子图合并契约）
    agents/registry.py      Agent 注册表（映射表路由："派给谁"）
    agents/runtime.py       AgentRuntime（编排图构建 / checkpointer / invoke / resume）
    agents/orchestrator.py  顶层调度中枢编排图（节点 + 条件边："怎么干"）
    agents/routing/         路由决策器（explicit / llm / hybrid）
    agents/tools/           工具注册中心（权限：只读可直调 / 写由人工执行）

新增业务 Agent：在 agents/ 中注册（AgentSpec）即可扩展，无需改编排层。
"""

from qingchuan_agent.agents import (
    AgentRegistry,
    AgentRuntime,
    AgentSpec,
    AgentTaskState,
    BaseAgent,
    OrchestratorState,
    agent_registry,
    get_agent_runtime,
)

__all__ = [
    "AgentRegistry",
    "AgentRuntime",
    "AgentSpec",
    "AgentTaskState",
    "BaseAgent",
    "OrchestratorState",
    "agent_registry",
    "get_agent_runtime",
]
