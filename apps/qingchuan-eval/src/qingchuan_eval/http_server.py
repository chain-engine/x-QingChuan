"""HTTP 入口：qingchuan-eval-server（按需触发的评测服务，供 CI / 运维面板调用）。

端点：
    GET  /eval/health        健康检查
    POST /eval/run           运行评测，body 见 EvalRunRequest

启动：uv run qingchuan-eval-server（端口默认 8030，可用 QINGCHUAN_EVAL_HOST/PORT 覆盖）
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ValidationError

from qingchuan_eval import __version__
from qingchuan_eval.report import print_summary
from qingchuan_eval.runner import run_eval
from qingchuan_eval.schema import EvalConfig, GoldenSetEntry, load_golden_set

_DEFAULT_GOLDEN_SET = Path(__file__).resolve().parents[2] / "data" / "golden_set.jsonl"

app = FastAPI(title="qingchuan-eval", version=__version__, description="晴川 RAG 评测服务")


class EvalRunRequest(BaseModel):
    """评测触发请求。golden_set 缺省取环境变量 QINGCHUAN_EVAL_GOLDEN_SET 或包内默认。"""

    golden_set: str | None = None
    config: dict[str, Any] = {}


@app.get("/eval/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "version": __version__}


def _load_entries(path: str) -> list[GoldenSetEntry]:
    """同步读取 golden set（存在性检查 + 解析），供 asyncio.to_thread 调用。"""
    if not Path(path).exists():
        raise FileNotFoundError(path)
    return load_golden_set(path)


@app.post("/eval/run")
async def eval_run(body: EvalRunRequest) -> dict[str, Any]:
    golden_path = (
        body.golden_set or os.environ.get("QINGCHUAN_EVAL_GOLDEN_SET") or str(_DEFAULT_GOLDEN_SET)
    )
    try:
        entries = await asyncio.to_thread(_load_entries, golden_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"golden set 不存在: {golden_path}") from None
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"golden set 解析失败: {e}") from e

    try:
        # 缺省字段取 EvalConfig 默认值，body.config 仅覆盖显式提供的字段
        merged = {**EvalConfig().model_dump(), **body.config}
        config = EvalConfig.model_validate(merged)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=f"config 校验失败: {e.errors()}") from e

    if config.max_samples:
        entries = entries[: config.max_samples]

    report = await asyncio.to_thread(run_eval, entries, config)
    print_summary(report)
    return report.model_dump(mode="json")


def main() -> None:
    import uvicorn

    host = os.environ.get("QINGCHUAN_EVAL_HOST", "0.0.0.0")
    port = int(os.environ.get("QINGCHUAN_EVAL_PORT", "8030"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
