"""编排层模块（晴川 x-QingChuan，对齐北辰 server/src/agents 形态）。

本包 = 编排运行时 + 业务编排单元，两层职责：

编排层（运行时）：
    base.py          BaseAgent 抽象基类（子图构建契约）
    state.py         共享状态 TypedDict（顶层编排 + 子图合并契约）
    registry.py      Agent 注册表（映射表路由："派给谁"）
    runtime.py       AgentRuntime（编排图构建 / checkpointer / invoke / resume）
    orchestrator.py  顶层调度中枢编排图（节点 + 条件边："怎么干"）
    routing/         路由决策器（explicit / llm / hybrid）
    tools/           工具注册中心（权限：只读可直调 / 写由人工执行）

业务层（编排单元）：
    agent_a 等       业务 Agent / 工作流模块（模块内完成注册，子图惰性编译）

新增业务 Agent：在本包新建模块并在此显式导入即可，无需改编排层。
"""

from qingchuan_agent.agents import (
    agent_a,
    tools,
)
from qingchuan_agent.agents.base import BaseAgent
from qingchuan_agent.agents.registry import AgentRegistry, AgentSpec, agent_registry
from qingchuan_agent.agents.runtime import AgentRuntime, get_agent_runtime
from qingchuan_agent.agents.state import AgentTaskState, OrchestratorState

__all__ = [
    "AgentRegistry",
    "AgentRuntime",
    "AgentSpec",
    "AgentTaskState",
    "BaseAgent",
    "OrchestratorState",
    "agent_a",
    "agent_registry",
    "get_agent_runtime",
    "tools",
]
