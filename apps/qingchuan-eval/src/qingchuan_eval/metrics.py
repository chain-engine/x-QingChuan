"""确定性评测指标（零 LLM 成本，可进 CI 回归）。

口径说明：
- hits: 与检索结果一一对应的 bool 列表（True=该位置命中 gold），按相关性降序。
- hit@k：前 k 个结果中至少一个命中（1.0/0.0），聚合取样本均值。
- MRR：首个命中位置的倒数。
- precision@k：前 k 个结果中命中比例（context precision 代理）。
- recall：被至少一个检索结果命中的 gold 片段数 / gold 片段总数。
- 答案指标（full 模式）：归一化包含率 + 字符级 F1。
"""

from __future__ import annotations

from collections.abc import Sequence

# 中文场景字符级切分即可（无需分词）；归一化在 matcher.normalize_text 完成


def hit_at_k(hits: Sequence[bool], k: int) -> float:
    """前 k 个结果是否命中 gold。"""
    return 1.0 if any(hits[:k]) else 0.0


def mrr(hits: Sequence[bool]) -> float:
    """首个命中位置的倒数（无命中返回 0）。"""
    for idx, hit in enumerate(hits, start=1):
        if hit:
            return 1.0 / idx
    return 0.0


def precision_at_k(hits: Sequence[bool], k: int) -> float:
    """前 k 个结果中的命中比例（k 超过结果数按结果数计）。"""
    top = hits[:k]
    if not top:
        return 0.0
    return sum(1 for h in top if h) / len(top)


def recall(matched_gold: int, gold_total: int) -> float:
    """gold 片段召回率。"""
    if gold_total <= 0:
        return 0.0
    return matched_gold / gold_total


def answer_containment(answer: str, reference: str) -> float:
    """归一化后标准答案是否包含于生成答案。"""
    n_answer, n_ref = _normalize(answer), _normalize(reference)
    if not n_ref:
        return 0.0
    return 1.0 if n_ref in n_answer else 0.0


def answer_f1(answer: str, reference: str) -> float:
    """字符级 F1（含中文标点归一化）。"""
    n_answer, n_ref = _normalize(answer), _normalize(reference)
    if not n_answer or not n_ref:
        return 0.0
    common = _char_multiset_intersection(n_answer, n_ref)
    if not common:
        return 0.0
    precision = common / len(n_answer)
    recall = common / len(n_ref)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def mean(values: Sequence[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _normalize(text: str) -> str:
    """小写 + 去全部空白 + NFKC 归一（中文场景字符级比对）。"""
    import unicodedata

    return "".join(unicodedata.normalize("NFKC", text.lower()).split())


def _char_multiset_intersection(a: str, b: str) -> int:
    from collections import Counter

    ca, cb = Counter(a), Counter(b)
    return sum((ca & cb).values())
