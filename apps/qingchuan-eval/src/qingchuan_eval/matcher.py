"""gold 命中判定：检索片段 ↔ 金标准片段引用。

主判定 = 归一化文本包含（snippet in chunk text）；
当 golden 提供 chunk_index 且检索片段元数据带 chunk_index 时，可做精确引用判定。
"""

from __future__ import annotations

from collections.abc import Iterable

from qingchuan_eval.schema import GoldChunkRef

# snippet 低于该长度时不做反向包含（避免过短片段误命中）
_REVERSE_MATCH_MIN_LEN = 24


def normalize_text(text: str) -> str:
    """小写 + 去全部空白 + NFKC 归一（中文场景包含匹配）。"""
    import unicodedata

    return "".join(unicodedata.normalize("NFKC", text.lower()).split())


def gold_hit(chunk: dict, ref: GoldChunkRef) -> bool:
    """单个检索片段是否命中单个 gold 引用。chunk 为 RetrievedChunk dict。"""
    chunk_text = chunk.get("text") or chunk.get("content") or ""
    n_chunk, n_snippet = normalize_text(chunk_text), normalize_text(ref.snippet)
    if not n_chunk or not n_snippet:
        return False

    # 精确引用（冻结 KB 状态）：chunk_index 一致即命中
    if ref.chunk_index is not None:
        meta_index = (chunk.get("metadata") or {}).get("chunk_index")
        if meta_index is not None and str(meta_index) == str(ref.chunk_index):
            return True

    # 文本包含：snippet 在 chunk 内；snippet 较长时允许 chunk 反向包含
    if n_snippet in n_chunk:
        return True
    if len(n_snippet) >= _REVERSE_MATCH_MIN_LEN and n_chunk in n_snippet:
        return True
    return False


def match_retrieved(retrieved: Iterable[dict], gold: list[GoldChunkRef]) -> tuple[list[bool], int]:
    """按检索顺序返回命中标记列表，以及被至少一个片段命中的 gold 引用数。

    Returns:
        (hits, matched_gold_count)
    """
    hits: list[bool] = []
    matched_refs: set[int] = set()
    for chunk in retrieved:
        hit = False
        for idx, ref in enumerate(gold):
            if gold_hit(chunk, ref):
                hit = True
                matched_refs.add(idx)
        hits.append(hit)
    return hits, len(matched_refs)
