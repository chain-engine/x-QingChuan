"""CLI 入口：qingchuan-eval run / qingchuan-eval validate。

示例：
    uv run qingchuan-eval run --golden-set data/golden_set.jsonl \
        --base-url http://127.0.0.1:8010 --mode retrieval --output eval-report.json
    uv run qingchuan-eval run --mode full --max-samples 20 \
        --threshold-hit-at-3 0.85 --threshold-mrr 0.6
    uv run qingchuan-eval validate --golden-set data/golden_set.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from qingchuan_eval.report import print_summary
from qingchuan_eval.runner import run_eval
from qingchuan_eval.schema import EvalConfig, load_golden_set

# 包内默认数据目录（apps/qingchuan-eval/data）
_DEFAULT_GOLDEN_SET = Path(__file__).resolve().parents[2] / "data" / "golden_set.jsonl"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="qingchuan-eval",
        description="晴川 RAG 评测：golden set 回归 + 确定性指标（CLI）",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="运行评测")
    run_p.add_argument("--golden-set", type=Path, default=_DEFAULT_GOLDEN_SET)
    run_p.add_argument("--base-url", default="http://127.0.0.1:8010")
    run_p.add_argument("--api-prefix", default="/api/v1")
    run_p.add_argument("--top-k", type=int, default=5)
    run_p.add_argument("--similarity-threshold", type=float, default=0.0)
    run_p.add_argument("--use-mmr", action="store_true")
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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.command == "validate":
        return _cmd_validate(args)

    return _cmd_run(args)


def _cmd_validate(args: argparse.Namespace) -> int:
    path = args.golden_set
    if not Path(path).exists():
        print(f"golden set 不存在: {path}", file=sys.stderr)
        return 1
    try:
        entries = load_golden_set(path)
    except Exception as e:
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
    golden_path = Path(args.golden_set)
    if not golden_path.exists():
        print(f"golden set 不存在: {golden_path}", file=sys.stderr)
        return 1

    config = EvalConfig(
        base_url=args.base_url,
        api_prefix=args.api_prefix,
        top_k=args.top_k,
        similarity_threshold=args.similarity_threshold,
        use_mmr=args.use_mmr,
        mode=args.mode,
        max_samples=args.max_samples,
        threshold_hit_at_3=args.threshold_hit_at_3,
        threshold_mrr=args.threshold_mrr,
        threshold_context_precision_at_3=args.threshold_context_precision_at_3,
        threshold_recall=args.threshold_recall,
    )

    try:
        entries = load_golden_set(golden_path)
    except Exception as e:
        print(f"golden set 加载失败: {e}", file=sys.stderr)
        return 1

    if args.category:
        entries = [e for e in entries if e.category == args.category]
    if args.difficulty:
        entries = [e for e in entries if e.difficulty == args.difficulty]
    if not entries:
        print("过滤后无样本，退出", file=sys.stderr)
        return 1
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


if __name__ == "__main__":
    raise SystemExit(main())
