#!/usr/bin/env python3
"""顶层路由决策器（晴川 x-QingChuan，对齐北辰形态）。

把"派给谁"的判断从 route 节点抽离为独立组件，便于单测替换 LLM / registry。

三种模式（Settings.route_mode）：
    - explicit：仅靠调用方显式 task_type 查表，缺失/非法即失败（骨架默认行为）
    - llm：忽略显式值，一律由 LLM 从已注册候选中选择
    - hybrid：显式 task_type 合法则直接命中（零成本、不调 LLM）；
              为空/未注册时提取自然语言交 LLM，非法/低置信/Mock/异常则回退失败

输入策略（对齐北辰共识）：
    - 主文本：白名单人话字段 message/query/question/description/remark/intent，取第一个非空；
    - ID 类（account_id/campaign_id/customer_id/customer_ids）不进 prompt，避免噪声。

骨架说明：晴川暂未接入 LLM 基础设施，llm / hybrid 模式在无 provider 时
自动回退失败，行为与北辰 Mock 阶段一致。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from qingchuan_agent.constants import RouteMode
from qingchuan_agent.core.logger import logger

if TYPE_CHECKING:
    from qingchuan_agent.agents.registry import AgentRegistry

# 合法路由模式集合（配置非法值时回退 hybrid）
_VALID_MODES: set[str] = {mode.mark for mode in RouteMode}

# 白名单人话字段（按优先级取第一个非空）
_TEXT_FIELDS: tuple[str, ...] = ("message", "query", "question", "description", "remark", "intent")


@dataclass
class RouteDecision:
    """一次路由决策结果。"""

    target_agent: str | None  # 最终派发目标（合法已注册类型）；None 表示未能路由
    mode_used: str  # explicit / llm / fallback / none
    confidence: float | None  # LLM 置信度；显式路由为 None
    reason: str  # 决策理由（审计/可观测）


class RouteResolver:
    """路由决策器。"""

    def __init__(
        self,
        registry: AgentRegistry,
        llm_provider: Any | None = None,
        mode: str | RouteMode = RouteMode.HYBRID,
        confidence_threshold: float = 0.7,
    ) -> None:
        self._registry = registry
        self._llm_provider = llm_provider
        mode_str = mode.mark if isinstance(mode, RouteMode) else str(mode)
        self._mode = mode_str if mode_str in _VALID_MODES else RouteMode.HYBRID.mark
        self._threshold = float(confidence_threshold)

    # ----------------------------------------------------------
    # 主入口
    # ----------------------------------------------------------

    def resolve(self, task_type: str | None, payload: dict[str, Any] | None) -> RouteDecision:
        """按模式决定目标 Agent。永不抛异常给编排主流程，失败以 target_agent=None 表达。"""
        payload = payload or {}
        explicit = str(task_type).strip() if task_type else ""

        # 1. 显式命中注册表：三种模式下都优先直接用，零成本不调 LLM
        if explicit and self._registry.has(explicit):
            return RouteDecision(explicit, RouteMode.EXPLICIT, None, "显式 task_type 命中注册表")

        # 2. explicit 模式：不尝试 LLM，缺失/非法即失败
        if self._mode == RouteMode.EXPLICIT.mark:
            return RouteDecision(
                None, "none", None, f"explicit 模式下无合法 task_type：{explicit or '(空)'}"
            )

        # 3. llm / hybrid：提取自然语言交 LLM
        query = self._extract_query(payload)
        if not query:
            return RouteDecision(
                None,
                "none",
                None,
                "缺少可路由的 task_type，且 payload 无自然语言描述",
            )

        decision = self._llm_classify(query)
        if decision.target_agent:
            return decision

        # 4. 回退：补充显式未注册说明
        reason = decision.reason
        if explicit:
            reason = f"显式 task_type={explicit} 未注册；{reason}"
        return RouteDecision(None, "fallback", decision.confidence, reason)

    # ----------------------------------------------------------
    # 自然语言提取
    # ----------------------------------------------------------

    def _extract_query(self, payload: dict[str, Any]) -> str:
        """白名单人话字段为主；ID 类字段丢弃。"""
        parts: list[str] = []
        for field in _TEXT_FIELDS:
            value = payload.get(field)
            if isinstance(value, str) and value.strip():
                parts.append(value.strip())
                break
        return "；".join(parts)

    # ----------------------------------------------------------
    # LLM 分类
    # ----------------------------------------------------------

    def _llm_classify(self, query: str) -> RouteDecision:
        """调 LLM 从注册候选中选择；Mock / 解析失败 / 非法 / 低置信 / 异常均回退。"""
        provider = self._llm_provider
        model = provider.get_chat_model() if provider is not None else None
        if model is None:
            return RouteDecision(None, "fallback", None, "未配置真实 LLM（Mock），跳过动态路由")

        options = self._registry.list_routing_options()
        if not options:
            return RouteDecision(None, "fallback", None, "注册表无可用 Agent 候选")

        candidates = "\n".join(
            f"- {o['type']}（{o['name']}）：{o['routing_hint']}" for o in options
        )
        messages = [
            {
                "role": "system",
                "content": f"你是任务路由分类器，只能从候选 Agent 中选择。候选列表：\n{candidates}",
            },
            {
                "role": "human",
                "content": (
                    f"请判断任务应分派给哪个 Agent，以 JSON 返回 "
                    f"agent_type/confidence/reason：{query}"
                ),
            },
        ]

        from langchain_core.messages import HumanMessage, SystemMessage

        lc_messages = [
            SystemMessage(content=m["content"])
            if m["role"] == "system"
            else HumanMessage(content=m["content"])
            for m in messages
        ]

        try:
            response = model.invoke(lc_messages)
            raw = str(getattr(response, "content", response))
        except Exception as exc:
            logger.exception(f"[Route] LLM 调用异常：{exc}")
            return RouteDecision(None, "fallback", None, f"LLM 调用异常：{exc}")

        parsed = self._parse_json(raw)
        if parsed is None:
            return RouteDecision(None, "fallback", None, "LLM 返回无法解析为路由 JSON")

        agent_type = str(parsed.get("agent_type") or "").strip()
        try:
            confidence = float(parsed.get("confidence") or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        reason = str(parsed.get("reason") or "").strip()

        if not self._registry.has(agent_type):
            return RouteDecision(
                None, "fallback", confidence, f"LLM 选择了未注册类型：{agent_type or '(空)'}"
            )
        if confidence < self._threshold:
            return RouteDecision(
                None,
                "fallback",
                confidence,
                f"置信度 {confidence:.2f} 低于阈值 {self._threshold:.2f}，不予采信",
            )
        logger.info(f"[Route] LLM 命中 {agent_type}（confidence={confidence:.2f}）：{reason}")
        return RouteDecision(agent_type, RouteMode.LLM, confidence, reason)

    @staticmethod
    def _parse_json(raw: str) -> dict[str, Any] | None:
        """从 LLM 输出中抽取首个 JSON 对象（容忍 ```json 围栏与前后说明文字）。"""
        if not raw:
            return None
        # 剥离 markdown 代码围栏
        cleaned = re.sub(r"```(?:json)?", "", raw).strip()
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except (json.JSONDecodeError, ValueError):
            return None
        return data if isinstance(data, dict) else None


__all__ = ["RouteDecision", "RouteResolver"]
