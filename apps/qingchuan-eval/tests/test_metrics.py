"""确定性指标单元测试。"""

from qingchuan_eval import metrics


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
