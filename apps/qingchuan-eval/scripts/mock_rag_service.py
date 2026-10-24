"""mock rag-service：本地无真实服务时的链路冒烟目标。

实现 POST /api/v1/rag/retrieve（响应包裹 {code,message,data,request_id}，
data={query,chunks,total}，chunks 为领域契约 RetrievedChunk 结构），用语料句子做 2-gram 重叠检索，返回 top_k 个
RetrievedChunk。仅用于 qingchuan-eval 的端到端冒烟，不代表真实检索质量。

用法：
    cd apps/qingchuan-eval
    uv run python scripts/mock_rag_service.py   # 端口 8010
    uv run qingchuan-eval run --base-url http://127.0.0.1:8010 --output /tmp/report.json
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

_STOP = set("吗呢吧啊什么多少怎么如何哪些哪个是否可以能否是的一了在")

app = FastAPI(title="mock-rag-service")


def _ngrams(text: str, n: int = 2) -> list[str]:
    text = re.sub(r"[\s，。；、：？！“”‘’（）《》,.;:!?()\-]", "", text.lower())
    return [text[i : i + n] for i in range(len(text) - n + 1)]


def _load_sentences() -> list[tuple[str, str]]:
    """返回 [(source, sentence)]：从语料文件切出句子。"""
    out: list[tuple[str, str]] = []
    for path in sorted((DATA_DIR / "corpus").glob("*.txt")):
        text = path.read_text(encoding="utf-8")
        body = text.split("----", 1)[-1]
        for para in re.split(r"\n\s*\n", body):
            for sent in re.split(r"(?<=[。；])", para):
                sent = sent.strip()
                if 10 <= len(sent) <= 300:
                    out.append((path.name, sent))
    return out


_SENTENCES = _load_sentences()
# 预计算 2-gram → 句子索引
_INDEX: dict[str, list[int]] = {}
for _i, (_src, _sent) in enumerate(_SENTENCES):
    for _g in set(_ngrams(_sent)):
        _INDEX.setdefault(_g, []).append(_i)


@app.post("/api/v1/rag/retrieve")
async def retrieve(request: Request) -> dict:
    body = await request.json()
    query: str = body.get("query", "")
    top_k: int = int(body.get("top_k", 5))
    grams = [g for g in _ngrams(query) if g not in _STOP and len(g) >= 2]
    scores: dict[int, int] = {}
    for g in grams:
        for i in _INDEX.get(g, []):
            scores[i] = scores.get(i, 0) + 1
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:top_k]
    chunks = []
    for i, score in ranked:
        src, sent = _SENTENCES[i]
        chunks.append(
            {
                "chunk_id": f"{uuid.uuid4()}_chunk_{i}",
                "document_id": str(uuid.uuid4()),
                "source": src,
                "text": sent,
                "score": round(score / max(len(grams), 1), 4),
                "metadata": {"source_file": src, "chunk_index": i},
            }
        )
    return {
        "code": 0,
        "message": "ok",
        "request_id": str(uuid.uuid4()),
        "data": {"query": query, "chunks": chunks, "total": len(chunks)},
    }


@app.post("/api/v1/rag/query")
async def query_rag(request: Request) -> dict:
    body = await request.json()
    query: str = body.get("query", "")
    top_k: int = int(body.get("top_k", 5))
    grams = [g for g in _ngrams(query) if g not in _STOP and len(g) >= 2]
    scores: dict[int, int] = {}
    for g in grams:
        for i in _INDEX.get(g, []):
            scores[i] = scores.get(i, 0) + 1
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:top_k]
    answer = "。".join(_SENTENCES[i][1] for i, _ in ranked)[:500] or "未检索到相关信息。"
    return {
        "code": 0,
        "message": "ok",
        "request_id": str(uuid.uuid4()),
        "data": {
            "query": query,
            "answer": answer,
            "retrieved_docs": [{"text": _SENTENCES[i][1]} for i, _ in ranked],
        },
    }


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8010)
