"""Agent 路由评测（explicit 模式，零成本可进 CI）。"""

from pathlib import Path

from qingchuan_agent.agents.registry import agent_registry
from qingchuan_agent.agents.routing.evaluator import (
    evaluate_route,
    load_route_golden_set,
)

_GOLDEN_SET = Path(__file__).resolve().parents[1] / "data" / "route_golden_set.jsonl"


def _entries():
    return load_route_golden_set(_GOLDEN_SET)


class TestLoadGoldenSet:
    def test_loads_all_samples(self):
        entries = _entries()
        assert len(entries) >= 30
        kinds = {e.kind for e in entries}
        assert kinds == {"explicit", "negative", "natural"}
        # 覆盖全部 5 类 Agent
        expected_types = {
            "content",
            "customer_service",
            "security",
            "data_analysis",
            "data_monitor",
        }
        assert expected_types <= {e.expected_agent for e in entries if e.kind == "explicit"}

    def test_unique_ids(self):
        ids = [e.id for e in _entries()]
        assert len(ids) == len(set(ids))


class TestExplicitRouteEval:
    def test_accuracy_100_percent_on_explicit_and_negative(self):
        report = evaluate_route(_entries(), mode="explicit", registry=agent_registry)
        # 20 explicit + 3 negative 参与判定；7 natural 在 explicit 下不判定
        assert report.judged == 23
        assert report.accuracy == 1.0
        judged = [s for s in report.samples if s.correct is not None]
        assert all(s.correct for s in judged)

    def test_natural_samples_not_judged_in_explicit(self):
        report = evaluate_route(_entries(), mode="explicit", registry=agent_registry)
        natural = [s for s in report.samples if s.kind == "natural"]
        assert len(natural) == 7
        assert all(s.correct is None for s in natural)

    def test_hybrid_without_llm_skips(self):
        report = evaluate_route(_entries(), mode="hybrid", registry=agent_registry)
        assert report.skipped_reason is not None
        assert report.accuracy is None
