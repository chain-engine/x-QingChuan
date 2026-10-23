"""检索片段上下文组装（晴川 x-QingChuan，agents/common）。

把检索命中的领域契约片段（RetrievedChunk）组装为带序号的
可注入上下文文本，供各 Agent 的 LLM 生成节点复用。
"""

from __future__ import annotations

from qingchuan_domain.schemas.retrieval import RetrievedChunk


def build_context(docs: list[RetrievedChunk]) -> str:
    """组装带序号的上下文文本（[片段1] ... [片段N]，空片段跳过）。"""
    parts = []
    for index, doc in enumerate(docs, start=1):
        text = str(doc.text or "").strip()
        if text:
            parts.append(f"[片段{index}] {text}")
    return "\n\n".join(parts)


__all__ = ["build_context"]
