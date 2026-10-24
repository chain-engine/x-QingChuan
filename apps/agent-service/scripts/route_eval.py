#!/usr/bin/env python3
"""Agent 路由评测 CLI（晴川 x-QingChuan）。

    # explicit 模式（零成本，可进 CI）
    uv run --package qingchuan-agent python apps/agent-service/scripts/route_eval.py \
        --mode explicit --output route-eval-report.json

    # hybrid 模式（需配置真实 LLM provider：QINGCHUAN_AGENT_AI_LLM_*）
    uv run --package qingchuan-agent python apps/agent-service/scripts/route_eval.py \
        --mode hybrid --output route-eval-report.json

退出码：explicit 模式 accuracy 低于 --min-accuracy（默认 1.0）时非 0；
hybrid 未配置 LLM 时跳过并返回 2。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from qingchuan_agent.agents.routing.evaluator import (
    evaluate_route,
    load_route_golden_set,
    print_route_summary,
)

_DEFAULT_GOLDEN_SET = Path(__file__).resolve().parents[1] / "data" / "route_golden_set.jsonl"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="route-eval",
        description="Agent 路由准确率评测（explicit / hybrid 模式）",
    )
    parser.add_argument("--golden-set", type=Path, default=_DEFAULT_GOLDEN_SET)
    parser.add_argument(
        "--mode",
        choices=["explicit", "hybrid", "llm"],
        default="explicit",
        help="路由模式（explicit 零成本可进 CI；hybrid/llm 需真实 LLM）",
    )
    parser.add_argument("--min-accuracy", type=float, default=1.0, help="最低准确率门槛")
    parser.add_argument("--confidence-threshold", type=float, default=0.7)
    parser.add_argument("--output", type=Path, default=None, help="报告 JSON 输出路径")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if not Path(args.golden_set).exists():
        print(f"route golden set 不存在: {args.golden_set}", file=sys.stderr)
        return 1
    try:
        entries = load_route_golden_set(args.golden_set)
    except Exception as e:
        print(f"route golden set 加载失败: {e}", file=sys.stderr)
        return 1

    llm_provider = None
    if args.mode in ("hybrid", "llm"):
        try:
            from qingchuan_agent.infras.llm import get_llm_provider

            llm_provider = get_llm_provider()
        except Exception as e:
            print(f"LLM provider 初始化失败（{e}），尝试缺省路由", file=sys.stderr)
            llm_provider = None

    report = evaluate_route(
        entries,
        mode=args.mode,
        llm_provider=llm_provider,
        confidence_threshold=args.confidence_threshold,
    )
    print_route_summary(report)

    if args.output:
        Path(args.output).write_text(report.model_dump_json(), encoding="utf-8")
        print(f"报告已写入: {args.output}")

    if report.skipped_reason:
        print(f"[跳过] {report.skipped_reason}", file=sys.stderr)
        return 2
    if report.accuracy is None:
        return 1
    if report.accuracy + 1e-9 < args.min_accuracy:
        print(
            f"[失败] 准确率 {report.accuracy:.1%} 低于门槛 {args.min_accuracy:.1%}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
