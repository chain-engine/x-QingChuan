"""确定性指标单元测试。"""

from qingchuan_eval import metrics
from qingchuan_eval.matcher import match_retrieved_detailed
from qingchuan_eval.schema import GoldChunkRef


class TestHitAtK:
    def test_first_hit(self):
        assert metrics.hit_at_k([True, True], 1) == 1.0

    def test_second_hit_not_in_top1(self):
        assert metrics.hit_at_k([False, True], 1) == 0.0

    def test_second_hit_in_top2(self):
        assert metrics.hit_at_k([False, True], 2) == 1.0

    def test_no_hit(self):
        assert metrics.hit_at_k([False, False, False], 3) == 0.0

    def test_k_beyond_length(self):
        assert metrics.hit_at_k([True], 5) == 1.0


class TestMRR:
    def test_third_rank(self):
        assert metrics.mrr([False, False, True]) == 1 / 3

    def test_first_rank(self):
        assert metrics.mrr([True, True]) == 1.0

    def test_no_hit(self):
        assert metrics.mrr([False, False]) == 0.0


class TestPrecisionAtK:
    def test_half(self):
        assert metrics.precision_at_k([True, False, True], 2) == 0.5

    def test_k_beyond_results(self):
        assert metrics.precision_at_k([True, False, True], 5) == 2 / 3

    def test_empty(self):
        assert metrics.precision_at_k([], 3) == 0.0


class TestRecall:
    def test_partial(self):
        assert metrics.recall(matched_gold=2, gold_total=4) == 0.5

    def test_zero_total(self):
        assert metrics.recall(matched_gold=0, gold_total=0) == 0.0


class TestRecallAtK:
    def _refs(self, per_chunk):
        return [set(idx) for idx in per_chunk]

    def test_cover_two_of_four_in_top2(self):
        refs = self._refs([[0], [2], [1], [3]])
        assert metrics.recall_at_k(refs, gold_total=4, k=2) == 0.5

    def test_grows_with_k(self):
        refs = self._refs([[0], [1], [2], [3]])
        assert metrics.recall_at_k(refs, gold_total=4, k=1) == 0.25
        assert metrics.recall_at_k(refs, gold_total=4, k=3) == 0.75
        assert metrics.recall_at_k(refs, gold_total=4, k=10) == 1.0

    def test_duplicate_refs_dedup(self):
        # 两个片段命中同一 gold 引用，去重后只计一次
        refs = self._refs([[0], [0], [1]])
        assert metrics.recall_at_k(refs, gold_total=3, k=2) == 1 / 3

    def test_zero_total(self):
        assert metrics.recall_at_k([], gold_total=0, k=3) == 0.0

    def test_end_to_end_with_matcher(self):
        gold = [
            GoldChunkRef(doc="d1", snippet="按月领取基本养老金"),
            GoldChunkRef(doc="d2", snippet="缴费基数申报"),
            GoldChunkRef(doc="d3", snippet="失业金领取期限"),
        ]
        retrieved = [
            {"text": "缴费基数申报指南全文。", "metadata": {}},
            {"text": "按月领取基本养老金的条件。", "metadata": {}},
            {"text": "无关内容。", "metadata": {}},
        ]
        _, _, refs_per_chunk = match_retrieved_detailed(retrieved, gold)
        assert metrics.recall_at_k(refs_per_chunk, gold_total=3, k=2) == 2 / 3
        assert metrics.recall_at_k(refs_per_chunk, gold_total=3, k=1) == 1 / 3


class TestAnswerMetrics:
    def test_containment_hit(self):
        assert metrics.answer_containment("根据规定，养老金按月领取。", "养老金 按月领取") == 1.0

    def test_containment_miss(self):
        assert metrics.answer_containment("完全无关的回答。", "养老金按月领取") == 0.0

    def test_f1_identical(self):
        assert metrics.answer_f1("养老金按月领取", "养老金按月领取") == 1.0

    def test_f1_disjoint(self):
        assert metrics.answer_f1("abc", "xyz") == 0.0

    def test_f1_partial(self):
        f1 = metrics.answer_f1("养老金的领取条件", "养老金")
        assert 0.0 < f1 <= 1.0

    def test_f1_empty(self):
        assert metrics.answer_f1("", "养老金") == 0.0


class TestMean:
    def test_mean(self):
        assert metrics.mean([1.0, 2.0, 3.0]) == 2.0

    def test_mean_empty(self):
        assert metrics.mean([]) is None
