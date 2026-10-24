"""控制台报告输出（聚合摘要 + 门禁判定；完整报告由 runner 以 JSON 落盘）。"""

from __future__ import annotations

from qingchuan_eval.schema import EvalReport


def print_summary(report: EvalReport) -> None:
    agg = report.aggregate
    print("=" * 56)
    print("晴川 RAG 评测报告")
    print(f"模式: {report.config.mode} | 样本: {agg.sample_count} | 错误率: {agg.error_rate:.1%}")
    print("-" * 56)
    print(f"  hit@1   : {fmt(agg.hit_at_1)}")
    print(f"  hit@3   : {fmt(agg.hit_at_3)}")
    print(f"  hit@5   : {fmt(agg.hit_at_5)}")
    print(f"  hit@10  : {fmt(agg.hit_at_10)}")
    print(f"  MRR     : {fmt(agg.mrr)}")
    print(f"  prec@3  : {fmt(agg.precision_at_3)}")
    print(f"  recall  : {fmt(agg.recall)}")
    print(
        f"  recall@1/3/5/10: {fmt(agg.recall_at_1)} / {fmt(agg.recall_at_3)} / "
        f"{fmt(agg.recall_at_5)} / {fmt(agg.recall_at_10)}"
    )
    if report.config.mode == "full":
        print(f"  答案包含率: {fmt(agg.answer_containment)}")
        print(f"  答案 F1   : {fmt(agg.answer_f1)}")
    print("-" * 56)
    if report.thresholds:
        for t in report.thresholds:
            mark = "PASS" if t.passed else ("--" if t.passed is None else "FAIL")
            print(f"  门禁 {t.metric}: {fmt(t.actual)} vs {t.threshold:.3f}  [{mark}]")
        verdict = report.all_thresholds_passed
        print(
            "  总体判定:",
            "通过" if verdict else ("未判定" if verdict is None else "不通过（回归风险）"),
        )
    else:
        print("  未配置门禁阈值（仅报告；计划 C 可配置 threshold_* 启用判定）")
    print("=" * 56)


def fmt(value: float | None) -> str:
    return "--" if value is None else f"{value:.3f}"
