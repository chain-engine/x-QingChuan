#!/usr/bin/env python3
"""Agent 路由准确率评测（晴川 x-QingChuan）。

目标：用 route golden set 度量 RouteResolver 的路由准确率，纳入 CI 门槛。

评测集样本类型（kind）：
    - explicit:      显式 task_type（合法）→ 期望命中对应 Agent（explicit 模式可评测）
    - negative:      显式 task_type 非法/未注册 → 期望路由失败（target_agent=None）
    - natural:       无 task_type，仅自然语言描述 → 期望 Agent（explicit 模式预期失败；
                     供 llm / hybrid 模式接入真实 LLM 后评测）

模式：
    - explicit（零成本，可进 CI）：仅判定 explicit / negative 样本；
    - hybrid / llm（需真实 LLM provider）：全部样本判定，未配置 provider 时跳过并告警。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from qingchuan_agent.agents.registry import AgentRegistry, agent_registry
from qingchuan_agent.agents.routing.resolver import RouteDecision, RouteResolver
from qingchuan_agent.constants import RouteMode


@dataclass(frozen=True)
class RouteGoldenEntry:
    """route golden set 单条样本。"""

    id: str
    query: str
    expected_agent: str | None
    kind: str = "explicit"  # explicit | negative | natural
    task_type: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    note: str | None = None


@dataclass
class RouteSampleResult:
    """单条样本路由判定结果。"""

    id: str
    kind: str
    query: str
    task_type: str | None
    expected_agent: str | None
    actual_agent: str | None
    mode_used: str
    confidence: float | None
    correct: bool | None = None  # None=该模式不做判定（如 natural × explicit）
    reason: str = ""


@dataclass
class RouteEvalReport:
    """路由评测报告。"""

    generated_at: str
    mode: str
    samples: list[RouteSampleResult]
    judged: int
    correct: int
    accuracy: float | None
    skipped_reason: str | None = None

    def write_json(self, path: str | Path) -> None:
        Path(path).write_text(self.model_dump_json(indent=2), encoding="utf-8")

    def model_dump_json(self, indent: int = 2) -> str:
        return json.dumps(
            {
                "generated_at": self.generated_at,
                "mode": self.mode,
                "judged": self.judged,
                "correct": self.correct,
                "accuracy": self.accuracy,
                "skipped_reason": self.skipped_reason,
                "samples": [
                    {
                        "id": s.id,
                        "kind": s.kind,
                        "query": s.query,
                        "task_type": s.task_type,
                        "expected_agent": s.expected_agent,
                        "actual_agent": s.actual_agent,
                        "mode_used": s.mode_used,
                        "confidence": s.confidence,
                        "correct": s.correct,
                        "reason": s.reason,
                    }
                    for s in self.samples
                ],
            },
            ensure_ascii=False,
            indent=indent,
        )


def load_route_golden_set(path: str | Path) -> list[RouteGoldenEntry]:
    """读取 JSONL route golden set，逐行校验；重复 id 报错。"""
    entries: list[RouteGoldenEntry] = []
    seen: set[str] = set()
    p = Path(path)
    with p.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            raw: dict[str, Any] = json.loads(line)
            kind = str(raw.get("kind") or "explicit")
            if kind not in ("explicit", "negative", "natural"):
                raise ValueError(f"{p}:{line_no} 非法 kind: {kind}")
            entry = RouteGoldenEntry(
                id=str(raw["id"]),
                query=str(raw["query"]),
                expected_agent=raw.get("expected_agent"),
                kind=kind,
                task_type=raw.get("task_type"),
                payload=raw.get("payload") or {},
                note=raw.get("note"),
            )
            if not entry.query.strip():
                raise ValueError(f"{p}:{line_no} query 不能为空")
            if entry.id in seen:
                raise ValueError(f"{p}:{line_no} 重复的 id: {entry.id}")
            seen.add(entry.id)
            entries.append(entry)
    return entries


def _is_judged(kind: str, mode: str) -> bool:
    """该 kind 样本在指定模式下是否参与判定。"""
    if kind == "explicit" or kind == "negative":
        return True
    if kind == "natural":
        # natural 样本需要 LLM 才能路由；explicit 模式无 LLM，预期失败且不计入准确率
        return mode in (RouteMode.HYBRID.mark, RouteMode.LLM.mark)
    return False


def evaluate_route(
    entries: list[RouteGoldenEntry],
    mode: str = RouteMode.EXPLICIT.mark,
    registry: AgentRegistry | None = None,
    llm_provider: Any | None = None,
    confidence_threshold: float = 0.7,
) -> RouteEvalReport:
    """对 golden set 执行一次路由评测（进程内直调 RouteResolver，无 HTTP 依赖）。

    Args:
        entries: golden set 样本
        mode: explicit | hybrid | llm
        registry: Agent 注册表（缺省全局单例）
        llm_provider: LLM provider（llm/hybrid 模式必需；显式模式忽略）
        confidence_threshold: LLM 置信度阈值

    Returns:
        路由评测报告（含逐样本判定与总体准确率）
    """
    reg = registry or agent_registry
    need_llm = mode in (RouteMode.HYBRID.mark, RouteMode.LLM.mark)
    if need_llm and llm_provider is None:
        return RouteEvalReport(
            generated_at=datetime.now(UTC).isoformat(),
            mode=mode,
            samples=[],
            judged=0,
            correct=0,
            accuracy=None,
            skipped_reason=(
                f"模式 {mode} 需要真实 LLM provider，未配置跳过；explicit 模式（零成本）可进 CI"
            ),
        )

    resolver = RouteResolver(
        registry=reg,
        llm_provider=llm_provider,
        mode=mode,
        confidence_threshold=confidence_threshold,
    )

    samples: list[RouteSampleResult] = []
    judged = 0
    correct = 0
    for entry in entries:
        decision: RouteDecision = resolver.resolve(entry.task_type, entry.payload)
        actual = decision.target_agent
        expected = entry.expected_agent
        sample = RouteSampleResult(
            id=entry.id,
            kind=entry.kind,
            query=entry.query,
            task_type=entry.task_type,
            expected_agent=expected,
            actual_agent=actual,
            mode_used=decision.mode_used,
            confidence=decision.confidence,
            reason=decision.reason,
        )
        if _is_judged(entry.kind, mode):
            judged += 1
            if expected is None:
                sample.correct = actual is None
            else:
                sample.correct = actual == expected
            if sample.correct:
                correct += 1
        samples.append(sample)

    accuracy = (correct / judged) if judged else None
    return RouteEvalReport(
        generated_at=datetime.now(UTC).isoformat(),
        mode=mode,
        samples=samples,
        judged=judged,
        correct=correct,
        accuracy=accuracy,
    )


def print_route_summary(report: RouteEvalReport) -> None:
    """控制台输出路由评测摘要。"""
    print("=" * 60)
    print("Agent 路由评测报告")
    print(f"模式: {report.mode} | 样本: {len(report.samples)}")
    if report.skipped_reason:
        print(f"跳过: {report.skipped_reason}")
        print("=" * 60)
        return
    print(
        f"判定: {report.judged}/{len(report.samples)} | "
        f"正确: {report.correct} | 准确率: "
        f"{'--' if report.accuracy is None else f'{report.accuracy:.1%}'}"
    )
    print("-" * 60)
    for s in report.samples:
        if s.correct is None:
            verdict = "未判定"
        else:
            verdict = "PASS" if s.correct else "FAIL"
        print(
            f"  [{verdict:>3}] {s.id:<20} kind={s.kind:<8} "
            f"expected={s.expected_agent or '(失败)':<18} "
            f"actual={s.actual_agent or '(失败)'}"
        )
        if s.correct is False:
            print(f"        reason: {s.reason[:120]}")
    print("=" * 60)


__all__ = [
    "RouteEvalReport",
    "RouteGoldenEntry",
    "RouteSampleResult",
    "evaluate_route",
    "load_route_golden_set",
    "print_route_summary",
]
