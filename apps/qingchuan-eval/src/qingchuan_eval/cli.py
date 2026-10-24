"""CLI 入口：qingchuan-eval run / validate / grid。

示例：
    uv run qingchuan-eval run --golden-set data/golden_set.jsonl \
        --base-url http://127.0.0.1:8010 --mode retrieval --output eval-report.json
    uv run qingchuan-eval run --mode full --max-samples 20 \
        --threshold-hit-at-3 0.85 --threshold-mrr 0.6
    uv run qingchuan-eval validate --golden-set data/golden_set.jsonl

网格调优（grid）：在 golden set 上遍历 top_k × 阈值 × MMR × RRF 组合，
按主指标排序输出最优参数（推荐分层使用，控制请求总量）：
    1）固定 MMR/RRF 关闭，调 top_k × threshold（3×3=9 组）
    2）固定最优 top_k，调 use_mmr × mmr_lambda × rrf_k（2×3×3=18 组）
全组合（3×3×2×3×3=162 组 × 113 条样本）会发起上万次检索请求，耗时较长，
可按 --max-samples 抽样收敛。

示例：
    uv run qingchuan-eval grid --base-url http://127.0.0.1:8010 \
        --top-ks 3,5,10 --thresholds 0.0,0.5,0.7 --use-mmrs 0 \
        --output data/grid/report.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from itertools import product
from pathlib import Path
from typing import Any

from qingchuan_eval.report import print_summary
from qingchuan_eval.runner import run_eval
from qingchuan_eval.schema import EvalConfig, load_golden_set

# 包内默认数据目录（apps/qingchuan-eval/data）
_DEFAULT_GOLDEN_SET = Path(__file__).resolve().parents[2] / "data" / "golden_set.jsonl"
_DEFAULT_GRID_DIR = Path(__file__).resolve().parents[2] / "data" / "grid"

# grid 主排序指标（None 值排后）
_GRID_METRICS: tuple[str, ...] = ("mrr", "hit_at_3", "hit_at_5", "recall_at_3", "recall")


def _parse_csv_ints(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _parse_csv_floats(raw: str) -> list[float]:
    return [float(x.strip()) for x in raw.split(",") if x.strip()]


def _parse_csv_bools(raw: str) -> list[bool]:
    out: list[bool] = []
    for x in raw.split(","):
        v = x.strip().lower()
        if v in ("1", "true", "yes", "on"):
            out.append(True)
        elif v in ("0", "false", "no", "off"):
            out.append(False)
        else:
            raise argparse.ArgumentTypeError(f"无法解析布尔值: {x!r}")
    return out


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="qingchuan-eval",
        description="晴川 RAG 评测：golden set 回归 + 确定性指标 + 参数网格调优（CLI）",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="运行评测")
    run_p.add_argument("--golden-set", type=Path, default=_DEFAULT_GOLDEN_SET)
    run_p.add_argument("--base-url", default="http://127.0.0.1:8010")
    run_p.add_argument("--api-prefix", default="/api/v1")
    run_p.add_argument("--top-k", type=int, default=5)
    run_p.add_argument("--similarity-threshold", type=float, default=0.0)
    run_p.add_argument("--use-mmr", action="store_true")
    run_p.add_argument("--mmr-lambda", type=float, default=0.5)
    run_p.add_argument("--rrf-k", type=int, default=None, help="RRF 融合常数（默认服务端 60）")
    run_p.add_argument("--mode", choices=["retrieval", "full"], default="retrieval")
    run_p.add_argument("--max-samples", type=int, default=None)
    run_p.add_argument("--category", default=None, help="按业务分类过滤，如 养老保险")
    run_p.add_argument(
        "--difficulty",
        default=None,
        help="按难度过滤：single_hop / multi_hop / boundary / filtered",
    )
    run_p.add_argument("--output", type=Path, default=None, help="报告 JSON 输出路径")
    run_p.add_argument("--threshold-hit-at-3", type=float, default=None)
    run_p.add_argument("--threshold-mrr", type=float, default=None)
    run_p.add_argument("--threshold-context-precision-at-3", type=float, default=None)
    run_p.add_argument("--threshold-recall", type=float, default=None)

    val_p = sub.add_parser("validate", help="校验 golden set 文件")
    val_p.add_argument("--golden-set", type=Path, default=_DEFAULT_GOLDEN_SET)

    grid_p = sub.add_parser("grid", help="参数网格调优（golden set 上遍历组合）")
    grid_p.add_argument("--golden-set", type=Path, default=_DEFAULT_GOLDEN_SET)
    grid_p.add_argument("--base-url", default="http://127.0.0.1:8010")
    grid_p.add_argument("--api-prefix", default="/api/v1")
    grid_p.add_argument("--top-ks", default="3,5,10", help="top_k 候选（逗号分隔）")
    grid_p.add_argument("--thresholds", default="0.0,0.5,0.7", help="相似度阈值候选")
    grid_p.add_argument("--use-mmrs", default="0,1", help="use_mmr 候选（0/1）")
    grid_p.add_argument("--mmr-lambdas", default="0.5", help="mmr_lambda 候选")
    grid_p.add_argument(
        "--rrf-ks", default="", help="RRF k 候选（如 30,60,90；留空=不参与网格，用服务端默认）"
    )
    grid_p.add_argument(
        "--metric",
        default="mrr",
        choices=list(_GRID_METRICS),
        help="主排序指标（默认 mrr）",
    )
    grid_p.add_argument("--max-samples", type=int, default=None, help="抽样条数（成本控制）")
    grid_p.add_argument("--category", default=None)
    grid_p.add_argument("--difficulty", default=None)
    grid_p.add_argument(
        "--output",
        type=Path,
        default=None,
        help="报告 JSON 输出路径（缺省写入 data/grid/ 带时间戳文件）",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.command == "validate":
        return _cmd_validate(args)
    if args.command == "grid":
        return _cmd_grid(args)
    return _cmd_run(args)


def _load_entries(golden_path: Path, category: str | None, difficulty: str | None) -> list[Any]:
    """加载 golden set 并按分类/难度过滤（grid 与 run 共用）。"""
    if not golden_path.exists():
        raise FileNotFoundError(f"golden set 不存在: {golden_path}")
    entries = load_golden_set(golden_path)
    if category:
        entries = [e for e in entries if e.category == category]
    if difficulty:
        entries = [e for e in entries if e.difficulty == difficulty]
    if not entries:
        raise ValueError("过滤后无样本，退出")
    return entries


def _cmd_validate(args: argparse.Namespace) -> int:
    path = args.golden_set
    try:
        entries = _load_entries(Path(path), None, None)
    except (FileNotFoundError, ValueError) as e:
        print(f"golden set 校验失败: {e}", file=sys.stderr)
        return 1
    print(f"golden set OK: {len(entries)} 条 | {path}")
    from collections import Counter

    by_cat = Counter(e.category for e in entries)
    by_diff = Counter(e.difficulty for e in entries)
    print("分类分布:", dict(by_cat))
    print("难度分布:", dict(by_diff))
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    try:
        entries = _load_entries(Path(args.golden_set), args.category, args.difficulty)
    except (FileNotFoundError, ValueError) as e:
        print(f"{e}", file=sys.stderr)
        return 1

    config = EvalConfig(
        base_url=args.base_url,
        api_prefix=args.api_prefix,
        top_k=args.top_k,
        similarity_threshold=args.similarity_threshold,
        use_mmr=args.use_mmr,
        mmr_lambda=args.mmr_lambda,
        rrf_k=args.rrf_k,
        mode=args.mode,
        max_samples=args.max_samples,
        threshold_hit_at_3=args.threshold_hit_at_3,
        threshold_mrr=args.threshold_mrr,
        threshold_context_precision_at_3=args.threshold_context_precision_at_3,
        threshold_recall=args.threshold_recall,
    )
    if config.max_samples:
        entries = entries[: config.max_samples]

    print(f"评测目标: {config.base_url} | 样本 {len(entries)} 条 | 模式 {config.mode}")
    report = run_eval(entries, config)
    print_summary(report)

    if args.output:
        report.write_json(args.output)
        print(f"报告已写入: {args.output}")
    else:
        # 无 --output 时仍打印一份报告 JSON 摘要（前 2 条失败样本），便于快速排查
        failed = [s for s in report.samples if s.error]
        if failed:
            print("失败样本示例:", json.dumps(failed[:2], ensure_ascii=False, indent=2))
    return 0 if report.all_thresholds_passed is not False else 1


def _cmd_grid(args: argparse.Namespace) -> int:
    try:
        entries = _load_entries(Path(args.golden_set), args.category, args.difficulty)
    except (FileNotFoundError, ValueError) as e:
        print(f"{e}", file=sys.stderr)
        return 1
    if args.max_samples:
        entries = entries[: args.max_samples]

    try:
        top_ks = _parse_csv_ints(args.top_ks)
        thresholds = _parse_csv_floats(args.thresholds)
        use_mmrs = _parse_csv_bools(args.use_mmrs)
        mmr_lambdas = _parse_csv_floats(args.mmr_lambdas)
        rrf_ks = _parse_csv_ints(args.rrf_ks) if args.rrf_ks.strip() else []
    except ValueError as e:
        print(f"参数解析失败: {e}", file=sys.stderr)
        return 1

    combos: list[dict[str, Any]] = []
    for top_k, thr, use_mmr, mmr_lambda, rrf_k in product(
        top_ks,
        thresholds,
        use_mmrs,
        mmr_lambdas,
        rrf_ks or [None],
    ):
        combos.append(
            {
                "top_k": top_k,
                "similarity_threshold": thr,
                "use_mmr": use_mmr,
                "mmr_lambda": mmr_lambda,
                "rrf_k": rrf_k,
            }
        )

    total_combos = len(combos)
    print(
        f"网格调优: {total_combos} 组 × {len(entries)} 条样本 | 目标 {args.base_url} | "
        f"主指标 {args.metric}"
    )
    print(
        f"top_ks={top_ks} thresholds={thresholds} use_mmrs={use_mmrs} "
        f"mmr_lambdas={mmr_lambdas} rrf_ks={rrf_ks or '(默认)'}"
    )

    runs: list[dict[str, Any]] = []
    for i, params in enumerate(combos, start=1):
        config = EvalConfig(
            base_url=args.base_url,
            api_prefix=args.api_prefix,
            top_k=params["top_k"],
            similarity_threshold=params["similarity_threshold"],
            use_mmr=params["use_mmr"],
            mmr_lambda=params["mmr_lambda"],
            rrf_k=params["rrf_k"],
            mode="retrieval",
            max_samples=None,
        )
        report = run_eval(entries, config)
        agg = report.aggregate
        runs.append(
            {
                **params,
                "sample_count": agg.sample_count,
                "error_rate": agg.error_rate,
                "hit_at_1": agg.hit_at_1,
                "hit_at_3": agg.hit_at_3,
                "hit_at_5": agg.hit_at_5,
                "hit_at_10": agg.hit_at_10,
                "mrr": agg.mrr,
                "precision_at_3": agg.precision_at_3,
                "recall": agg.recall,
                "recall_at_3": agg.recall_at_3,
                "recall_at_5": agg.recall_at_5,
            }
        )
        if i % 10 == 0 or i == total_combos:
            print(f"  进度 {i}/{total_combos}")

    runs.sort(
        key=lambda r: (r.get(args.metric) is not None, r.get(args.metric) or 0.0),
        reverse=True,
    )

    _print_grid_table(runs, metric=args.metric)

    best = runs[0] if runs else None
    report_data = {
        "generated_at": datetime.now(UTC).isoformat(),
        "base_url": args.base_url,
        "sample_count": len(entries),
        "metric": args.metric,
        "combos": total_combos,
        "best": best,
        "runs": runs,
    }

    output = args.output or _DEFAULT_GRID_DIR / f"grid-{datetime.now(UTC):%Y%m%dT%H%M%S}.json"
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"网格报告已写入: {output}")

    if best:
        print(f"\n推荐参数（按 {args.metric} 排序最优）：")
        print(
            f"  top_k={best['top_k']} threshold={best['similarity_threshold']} "
            f"use_mmr={best['use_mmr']} mmr_lambda={best['mmr_lambda']} "
            f"rrf_k={best['rrf_k'] or '默认'}"
        )
        print(
            f"  hit@3={_fmt(best.get('hit_at_3'))} MRR={_fmt(best.get('mrr'))} "
            f"recall@3={_fmt(best.get('recall_at_3'))} recall={_fmt(best.get('recall'))}"
        )
    return 0


def _print_grid_table(runs: list[dict[str, Any]], metric: str) -> None:
    """控制台输出参数 → 指标表（前 15 行，纯文本无需额外依赖）。"""
    header = (
        f"{'top_k':>5} {'thr':>4} {'mmr':>4} {'lambda':>6} {'rrf_k':>6} "
        f"{'hit@3':>6} {'MRR':>6} {'recall@3':>8} {'recall':>6} {'err':>5}"
    )
    print("\n" + header)
    print("-" * len(header))
    shown = 0
    for r in runs:
        if shown >= 15 and len(runs) > 15:
            print("  ...（仅展示前 15 行，完整见报告 JSON）")
            break
        rrf = r["rrf_k"] if r["rrf_k"] is not None else "默认"
        print(
            f"{r['top_k']:>5} {r['similarity_threshold']:>4.2f} "
            f"{1 if r['use_mmr'] else 0:>4} {r['mmr_lambda']:>6.2f} {rrf:>6} "
            f"{_fmt(r.get('hit_at_3')):>6} {_fmt(r.get('mrr')):>6} "
            f"{_fmt(r.get('recall_at_3')):>8} {_fmt(r.get('recall')):>6} "
            f"{r.get('error_rate', 0.0):>5.2%}"
        )
        shown += 1
    print()


def _fmt(value: float | None) -> str:
    return "--" if value is None else f"{value:.3f}"


if __name__ == "__main__":
    raise SystemExit(main())
