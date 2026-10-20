#!/usr/bin/env python3
"""Agent 注册表（映射表路由的标准实现，晴川 x-QingChuan，对齐北辰形态）。

职责：
    1. 注册：agent_type → AgentSpec（含子图惰性构建器）
    2. 路由：task_type → AgentSpec（"派给谁"由映射表决定）
    3. 编译缓存：子图只编译一次，重复复用

与 LangGraph 的分工（对齐北辰共识）：
    - 注册表回答"派给谁"（task_type → Agent 的静态映射）
    - LangGraph 回答"怎么干"（子图内部步骤 / 生命周期 / 中断恢复）
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from qingchuan_agent.agents.base import BaseAgent
from qingchuan_agent.core.logger import logger

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph


@dataclass
class AgentSpec:
    """Agent 规格：注册表的一条记录，持有 Agent 对象门面。"""

    agent: BaseAgent
    enabled: bool = True
    # 路由提示：该 Agent 适配的典型场景 / 话术，供 LLM 动态路由构造候选；缺省回退 description
    routing_hint: str = ""

    @property
    def agent_type(self) -> str:
        return self.agent.agent_type

    @property
    def name(self) -> str:
        return self.agent.name

    @property
    def description(self) -> str:
        return self.agent.description


class AgentRegistry:
    """Agent 注册表（应用级单例，持编译缓存）。"""

    def __init__(self) -> None:
        self._specs: dict[str, AgentSpec] = {}
        self._graphs: dict[str, CompiledStateGraph] = {}

    # ----------------------------------------------------------
    # 注册
    # ----------------------------------------------------------

    def register(self, spec: AgentSpec) -> None:
        key = str(spec.agent_type)
        if key in self._specs:
            logger.warning(f"Agent 重复注册，覆盖旧定义：{key}")
        self._specs[key] = spec
        logger.info(f"Agent 注册成功：{key}（{spec.name}）")

    # ----------------------------------------------------------
    # 查询 / 路由
    # ----------------------------------------------------------

    def get_spec(self, agent_type: str) -> AgentSpec | None:
        """根据 agent_type 获取 AgentSpec。"""
        return self._specs.get(str(agent_type))

    def get_graph(self, agent_type: str) -> CompiledStateGraph:
        """获取编译后的子图（惰性编译 + 缓存）。"""
        key = str(agent_type)
        spec = self._specs.get(key)
        if spec is None:
            raise KeyError(f"Agent 未注册：{key}。可注册类型：{list(self._specs)}")
        if key not in self._graphs:
            self._graphs[key] = spec.agent.build()
            logger.info(f"Agent 子图编译完成：{key}")
        return self._graphs[key]

    def route(self, task_type: str) -> AgentSpec:
        """映射表路由：task_type → AgentSpec。"""
        spec = self.get_spec(task_type)
        if spec is None:
            raise KeyError(f"无法路由任务：{task_type}，未注册对应 Agent")
        if not spec.enabled:
            raise ValueError(f"Agent 已停用：{task_type}")
        return spec

    def list_specs(self) -> list[AgentSpec]:
        return list(self._specs.values())

    def list_routing_options(self) -> list[dict[str, str]]:
        """动态路由候选清单（供 LLM 选择）：仅含启用 Agent，不硬编码枚举。

        返回 [{type, name, description, routing_hint}, ...]，routing_hint 缺省回退 description。
        新增 Agent 注册后自动纳入，无需改路由提示词。
        """
        options: list[dict[str, str]] = []
        for spec in self._specs.values():
            if not spec.enabled:
                continue
            options.append(
                {
                    "type": str(spec.agent_type),
                    "name": spec.name,
                    "description": spec.description,
                    "routing_hint": spec.routing_hint or spec.description,
                }
            )
        return options

    def has(self, agent_type: str) -> bool:
        return str(agent_type) in self._specs


# ============================================================
# 全局单例：晴川 Agent 注册表
# ============================================================

agent_registry: AgentRegistry = AgentRegistry()

# 说明：骨架当前仅注册 Agent A（RAG 问答，占位）；后续面向湖北省人社
# 平台的新 Agent 在此 register 即可扩展（子图在首次被路由时惰性编译）。

__all__ = ["AgentRegistry", "AgentSpec", "agent_registry"]
