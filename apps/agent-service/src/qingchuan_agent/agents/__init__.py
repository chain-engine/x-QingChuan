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
    common/          公共编排能力（payload 提取 / 上下文组装 / todo 占位 / LLM 调用）

业务层（编排单元，五大分类，目录结构保持一致）：
    content/           内容创作 Agent（选题 → 生成 → 审核）
    customer_service/  问答（客服）Agent（原问答 Agent 更名：检索 → 生成）
    security/          安全 Agent（采集 → 风险分析 → 告警）
    data_analysis/     数据分析 Agent（取数 → 分析 → 报告）
    data_monitor/      数据监控 Agent（查询 → 判定 → 通知）

新增业务 Agent：在本包新建同构目录并在此显式导入即可，无需改编排层。
"""

from qingchuan_agent.agents import (
    content,
    customer_service,
    data_analysis,
    data_monitor,
    security,
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
    "agent_registry",
    "content",
    "customer_service",
    "data_analysis",
    "data_monitor",
    "get_agent_runtime",
    "security",
    "tools",
]
