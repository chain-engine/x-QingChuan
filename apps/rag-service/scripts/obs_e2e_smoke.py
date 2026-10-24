"""端到端冒烟：真实 Langfuse 自托管（localhost:3000）完整闭环。

事件流 → ObservabilityManager → LangfuseProvider → flush → v2 API 验证 trace 落库。
前置：`deploy/langfuse` 栈已启动（docker compose up -d）。
用法：uv run python scripts/obs_e2e_smoke.py
"""

import base64
import json
import os
import time
import urllib.request
import uuid
from datetime import UTC, datetime

os.environ["LANGFUSE_HOST"] = "http://127.0.0.1:3000"
os.environ["LANGFUSE_PUBLIC_KEY"] = "pk-local-qingchuan"
os.environ["LANGFUSE_SECRET_KEY"] = "sk-local-qingchuan"

from qingchuan_rag.core.config import settings  # noqa: E402
from qingchuan_rag.core.observability import (  # noqa: E402
    manager,
    reset_request_id,
    set_request_id,
)
from qingchuan_rag.core.observability.events import (  # noqa: E402
    GenerationEvent,
    RagQueryEvent,
    RetrievalPhaseEvent,
)

# 1. 初始化（真实 client 连接自托管）
manager.initialize(settings)
langfuse_prov = next((p for p in manager.providers if p.name == "langfuse"), None)
assert langfuse_prov is not None and langfuse_prov._client is not None, "LangfuseProvider 未激活"
print(f"[1] providers={[p.name for p in manager.providers]}  langfuse active=OK")

# 2. 发一条完整请求的事件流
rid = f"smoke-{uuid.uuid4().hex[:8]}"
now = datetime.now(UTC)
tok = set_request_id(rid)
try:
    manager.emit(RetrievalPhaseEvent(stage="understand", latency_ms=2.5, started_at=now, ended_at=now))
    manager.emit(RetrievalPhaseEvent(stage="candidate", latency_ms=9.0, candidates=12, started_at=now, ended_at=now))
    manager.emit(RetrievalPhaseEvent(stage="rank_filter", latency_ms=6.0, candidates=12, retrieved=4, started_at=now, ended_at=now))
    manager.emit(RetrievalPhaseEvent(stage="total", latency_ms=17.5, candidates=12, retrieved=4, started_at=now, ended_at=now))
    manager.emit(
        GenerationEvent(
            tokens={"prompt_tokens": 210, "completion_tokens": 96, "total_tokens": 306},
            model="deepseek-v3",
            latency_ms=420.0,
            started_at=now,
            ended_at=now,
        )
    )
    manager.emit(
        RagQueryEvent(
            query="武汉退休金怎么计算",
            query_len=9,
            top_k=4,
            latencies={"retrieval": 17.5, "generation": 420.0, "total": 440.0},
            tokens={"prompt_tokens": 210, "completion_tokens": 96, "total_tokens": 306},
            provider="deepseek",
            model="deepseek-v3",
            status="ok",
            error_type=None,
            started_at=now,
            ended_at=now,
        )
    )
finally:
    reset_request_id(tok)
print(f"[2] events emitted for trace={rid}")

# 3. flush 并等待 ingestion 落库
manager.shutdown()
print("[3] manager shutdown (flush) done, waiting for ingestion...")
time.sleep(6)

# 4. 通过 v4 实时查询层（UI 数据源）验证 trace 可见
auth = base64.b64encode(b"pk-local-qingchuan:sk-local-qingchuan").decode()
req = urllib.request.Request(
    "http://127.0.0.1:3000/api/public/v2/observations?page=1&limit=20",
    headers={"Authorization": "Basic " + auth},
)
with urllib.request.urlopen(req, timeout=10) as r:
    data = json.loads(r.read())
names = {o.get("name") for o in data["data"]}
assert "rag_query" in names and "retrieval" in names and "generation" in names, (
    f"v2 observations 缺少预期 span，got={sorted(names)}"
)
print(f"[4] v2 API 可见 {len(data['data'])} 条 observations（rag_query/retrieval/generation 均在），E2E SMOKE OK")

