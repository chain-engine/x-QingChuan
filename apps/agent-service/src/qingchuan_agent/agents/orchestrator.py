#!/usr/bin/env python3
"""顶层调度中枢编排图（晴川 x-QingChuan，对齐北辰 Hybrid 分层混合形态）。

图结构（节点 + 条件边 + 状态）：
    START ──▶ route（RouteResolver 决策：explicit 查表 / llm 动态选 / hybrid 显式优先兜底）
                   │
                   ├─ conditional（按 target_agent 分发到对应子图）
                   ▼
              已注册业务子图节点 ──▶ aggregate（聚合）──▶ END
              （后续注册的新 Agent 子图自动挂载，无需改图结构）

关键设计（对齐北辰 LangGraph 标准）：
    - 编译后的业务子图直接 add_node 注册为顶层图节点
      （框架统一处理嵌套 checkpoint / interrupt / resume，无需手动 invoke）
    - 路由决策抽离为 RouteResolver：显式 task_type 合法直接命中（不调 LLM）；
      为空/未注册时按自然语言交 LLM 从注册候选中选，非法/低置信/Mock 回退失败；
      route 节点只把最终 target_agent 写入状态，条件边按它分发到对应子图
    - 子图私有字段不声明在 OrchestratorState，输出自动忽略，不污染顶层

职责划分（对齐北辰共识）：
    - 编排图：管"怎么干" —— 派活链路、子图生命周期、中断恢复、结果聚合
    - RouteResolver：管"派给谁" —— 显式查表 + LLM 动态选择（注册表提供合法候选清单）
    - 注册表：管"有谁可用" —— 已注册 Agent 清单与子图查找（LLM 只能从中选，不能凭空造）
    - 业务子图：管"具体干" —— 各 Agent 内部步骤（新注册 Agent 自行实现）
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Any

from langgraph.graph import END, START, StateGraph

from qingchuan_agent.agents.registry import AgentRegistry
from qingchuan_agent.agents.state import OrchestratorState
from qingchuan_agent.constants import TaskStatus
from qingchuan_agent.core.logger import logger

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph

    from qingchuan_agent.agents.routing import RouteResolver


# ------------------------------------------------------------
# 节点实现
# ------------------------------------------------------------

def route_node(state: OrchestratorState, resolver: RouteResolver | None = None) -> dict[str, Any]:
    """路由节点：委托 RouteResolver 决定目标 Agent（explicit / llm / hybrid）。

    决策结果写入 target_agent，并把路由方式/置信度/理由一并落状态用于审计；
    未能路由（target_agent=None）直接抛错，交由 runtime 标记失败，不让空值进入条件边。
    """
    if resolver is None:
        raise RuntimeError("route_node 缺少 resolver（build 时未 partial 绑定）")
    decision = resolver.resolve(state.get("task_type"), state.get("payload"))
    if not decision.target_agent:
        raise RuntimeError(f"路由失败：{decision.reason}")
    logger.info(
        f"[Orchestrator] route: {state.get('task_type') or '(空)'} → "
        f"{decision.target_agent}（mode={decision.mode_used}, "
        f"confidence={decision.confidence}, reason={decision.reason}）"
    )
    return {
        "target_agent": decision.target_agent,
        "route_mode": decision.mode_used,
        "route_confidence": decision.confidence,
        "route_reason": decision.reason,
    }


def route_to_target(state: OrchestratorState) -> str:
    """条件边路由函数：返回目标子图节点名。"""
    target = state.get("target_agent")
    if not target:
        raise RuntimeError("未收到 target_agent（路由节点未执行？）")
    return target


def aggregate_node(state: OrchestratorState) -> dict[str, Any]:
    """聚合节点：归一化最终结果与状态，供 service 层落库/回写。

    子图节点输出（status/result/error/events）已由 LangGraph
    自动合并进顶层状态，这里做最终归一化。
    """
    status = state.get("status", TaskStatus.SUCCESS)
    logger.info(f"[Orchestrator] aggregate: status={status}")
    return {
        "status": status,
        "result": state.get("result") or {},
    }


# ------------------------------------------------------------
# 编排图构建
# ------------------------------------------------------------

def build_orchestrator_graph(
    registry: AgentRegistry,
    checkpointer: Any | None = None,
    *,
    llm_provider: Any | None = None,
    route_mode: str | None = None,
    confidence_threshold: float | None = None,
) -> CompiledStateGraph:
    """构建顶层调度中枢编排图。

    Args:
        registry: Agent 注册表（路由候选与子图查找）
        checkpointer: 检查点（memory/redis），子图 interrupt 依赖父图 checkpointer
        llm_provider: LLM 提供方；骨架缺省 None（动态路由自动回退），便于测试替身
        route_mode: 路由模式（RouteMode 枚举）；缺省取 settings.route_mode
        confidence_threshold: LLM 路由采信阈值；缺省取 settings.confidence_threshold

    Returns:
        编译后的顶层编排图
    """
    # 惰性构造路由决策器，避免编排层初始化时拉入 LLM 依赖
    from qingchuan_agent.agents.routing import RouteResolver
    from qingchuan_agent.core.config import get_settings

    settings = get_settings()
    if route_mode is None:
        route_mode = settings.agent.route_mode
    if confidence_threshold is None:
        confidence_threshold = settings.agent.confidence_threshold

    resolver = RouteResolver(
        registry,
        llm_provider=llm_provider,
        mode=route_mode,
        confidence_threshold=confidence_threshold,
    )

    graph = StateGraph(OrchestratorState)
    graph.add_node("route", partial(route_node, resolver=resolver))

    # 编译后的业务子图直接注册为顶层图节点（LangGraph 官方嵌套形态）
    route_map: dict[str, str] = {}
    for spec in registry.list_specs():
        key = str(spec.agent_type)
        graph.add_node(key, registry.get_graph(key))
        route_map[key] = key
        logger.info(f"[Orchestrator] 子图节点已挂载：{key}")

    # 增加聚合节点
    graph.add_node("aggregate", aggregate_node)

    # 增加路由边
    graph.add_edge(START, "route")
    # 增加条件路由边：route 之后按 target_agent 分发到对应子图节点
    graph.add_conditional_edges("route", route_to_target, route_map)
    # 每个子图节点结束后汇入聚合节点
    for key in route_map:
        graph.add_edge(key, "aggregate")
    graph.add_edge("aggregate", END)

    compiled = graph.compile(checkpointer=checkpointer)
    return compiled


__all__ = ["aggregate_node", "build_orchestrator_graph", "route_node", "route_to_target"]
