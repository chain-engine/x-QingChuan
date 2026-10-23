#!/usr/bin/env python3
"""Agent 抽象基类（晴川 x-QingChuan，对齐北辰形态）。

定义业务 Agent 子图的构建契约：
    每个业务 Agent = 一张独立编译的 LangGraph 子图（Subgraph），
    内嵌到顶层调度中枢编排图后成为"Agent 节点"。

两个层次（与北辰共识一致）：
    - 业务 Agent 用一张图实现（子图内部 = 节点 + 条件边 + 状态机）
    - 顶层调度用另一张图编排（编排图 = 路由节点 + 子图节点 + 聚合节点）
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from langgraph.graph.state import CompiledStateGraph

from qingchuan_agent.constants import AgentType


class BaseAgent(ABC):
    """业务 Agent 抽象基类。

    子类实现：
        agent_type   —— 注册表路由键（AgentType 枚举）
        name         —— 展示名
        description  —— 职责说明
        routing_hint —— 路由提示（LLM 动态路由构造候选；缺省回退 description）
        build()      —— 构建并返回编译好的子图
    """

    agent_type: AgentType
    name: str = ""
    description: str = ""
    routing_hint: str = ""

    @abstractmethod
    def build(self) -> CompiledStateGraph:
        """构建本 Agent 的 LangGraph 子图（已 compile）。

        骨架约定：步骤节点全部预留（todo/mock），接入真实业务时
        只需替换节点函数内部实现，图结构保持不变。
        """

    @property
    def route_key(self) -> str:
        """路由键（= agent_type），供映射表路由使用。"""
        return self.agent_type

    @property
    def effective_routing_hint(self) -> str:
        """路由提示：显式配置优先，缺省回退 description（注册表候选清单用）。"""
        return self.routing_hint or self.description

    def __repr__(self) -> str:  # pragma: no cover
        return f"<{self.__class__.__name__} type={self.agent_type} name={self.name}>"
