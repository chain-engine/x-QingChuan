"""评测执行器：golden set → rag-service 黑盒检索/问答 → 指标与报告。"""

from __future__ import annotations

from datetime import UTC, datetime

from qingchuan_eval import metrics
from qingchuan_eval.client import EvalClientError, RagClient
from qingchuan_eval.matcher import match_retrieved
from qingchuan_eval.schema import (
    EVAL_TOP_KS,
    AggregateMetrics,
    EvalConfig,
    EvalReport,
    GoldenSetEntry,
    SampleResult,
    ThresholdResult,
)


def run_eval(entries: list[GoldenSetEntry], config: EvalConfig) -> EvalReport:
    """执行一次评测，返回机器可读报告。

    mode=retrieval：仅检索侧指标（零 LLM 成本）；
    mode=full：叠加 /rag/query 生成侧指标（受 max_samples 控制成本）。
    """
    samples: list[SampleResult] = []
    with RagClient(config) as client:
        for entry in entries:
            samples.append(_eval_one(client, entry, config))

    aggregate = _aggregate(samples)
    thresholds = _evaluate_thresholds(aggregate, config)
    all_passed = (
        all(t.passed for t in thresholds)
        if thresholds and all(t.passed is not None for t in thresholds)
        else None
    )
    return EvalReport(
        generated_at=datetime.now(UTC).isoformat(),
        config=config,
        aggregate=aggregate,
        samples=samples,
        thresholds=thresholds,
        all_thresholds_passed=all_passed,
    )


def _eval_one(client: RagClient, entry: GoldenSetEntry, config: EvalConfig) -> SampleResult:
    base = SampleResult(
        id=entry.id,
        question=entry.question,
        category=entry.category,
        difficulty=entry.difficulty,
        gold_total=len(entry.gold),
    )
    try:
        retrieved = client.retrieve(query=entry.question)
    except EvalClientError as e:
        base.error = str(e)
        return base

    hits, matched_gold = match_retrieved(retrieved, entry.gold)
    base.retrieved_count = len(retrieved)
    base.hits = hits
    base.matched_gold_count = matched_gold

    base.hit_at_3 = metrics.hit_at_k(hits, 3)
    base.hit_at_5 = metrics.hit_at_k(hits, 5)
    base.mrr = metrics.mrr(hits)
    base.precision_at_3 = metrics.precision_at_k(hits, 3)
    base.recall = metrics.recall(matched_gold, len(entry.gold))

    if config.mode == "full" and entry.reference_answer:
        try:
            result = client.query(query=entry.question, top_k=config.top_k)
            answer = (result.get("answer") or "").strip()
            base.answer = answer or None
            if answer:
                base.answer_containment = metrics.answer_containment(answer, entry.reference_answer)
                base.answer_f1 = metrics.answer_f1(answer, entry.reference_answer)
        except EvalClientError as e:
            base.error = (base.error or "") + f" [query 失败: {e}]"
    return base


def _aggregate(samples: list[SampleResult]) -> AggregateMetrics:
    def avg(attr: str) -> float | None:
        values = [getattr(s, attr) for s in samples if getattr(s, attr) is not None]
        return metrics.mean(values)

    ok = [s for s in samples if not s.error]
    hit = {k: metrics.mean([metrics.hit_at_k(s.hits, k) for s in ok]) for k in EVAL_TOP_KS}
    prec = {k: metrics.mean([metrics.precision_at_k(s.hits, k) for s in ok]) for k in EVAL_TOP_KS}

    return AggregateMetrics(
        sample_count=len(samples),
        hit_at_1=hit[1],
        hit_at_3=hit[3],
        hit_at_5=hit[5],
        hit_at_10=hit[10],
        mrr=avg("mrr"),
        precision_at_1=prec[1],
        precision_at_3=prec[3],
        precision_at_5=prec[5],
        recall=avg("recall"),
        answer_containment=avg("answer_containment"),
        answer_f1=avg("answer_f1"),
        error_rate=(len(samples) - len(ok)) / len(samples) if samples else 0.0,
    )


def _evaluate_thresholds(agg: AggregateMetrics, config: EvalConfig) -> list[ThresholdResult]:
    specs = [
        ("threshold_hit_at_3", "hit@3", agg.hit_at_3),
        ("threshold_mrr", "MRR", agg.mrr),
        ("threshold_context_precision_at_3", "context precision@3", agg.precision_at_3),
        ("threshold_recall", "context recall", agg.recall),
    ]
    results: list[ThresholdResult] = []
    for attr, metric_name, actual in specs:
        threshold = getattr(config, attr)
        if threshold is None:
            continue
        results.append(
            ThresholdResult(
                metric=metric_name,
                threshold=threshold,
                actual=actual,
                passed=None if actual is None else actual >= threshold,
            )
        )
    return results
