"""gold 命中判定单元测试。"""

from qingchuan_eval.matcher import gold_hit, match_retrieved, normalize_text
from qingchuan_eval.schema import GoldChunkRef


class TestNormalizeText:
    def test_strip_whitespace_and_lower(self):
        assert normalize_text("  养老 保险 \n 待遇 ") == "养老保险待遇"

    def test_nfkc(self):
        assert normalize_text("ＡＢＣ") == "abc"


class TestGoldHit:
    def test_snippet_in_chunk(self):
        chunk = {
            "text": "参加基本养老保险的个人，达到法定退休年龄时累计缴费满十五年的，"
            "按月领取基本养老金。"
        }
        ref = GoldChunkRef(doc="doc", snippet="累计缴费满十五年的，按月领取基本养老金")
        assert gold_hit(chunk, ref)

    def test_chunk_index_exact(self):
        chunk = {"text": "其他内容", "metadata": {"chunk_index": "3"}}
        ref = GoldChunkRef(doc="doc", snippet="其他内容", chunk_index=3)
        assert gold_hit(chunk, ref)

    def test_no_match(self):
        chunk = {"text": "医疗保险待遇支付范围。", "metadata": {}}
        ref = GoldChunkRef(doc="doc", snippet="养老金领取条件")
        assert not gold_hit(chunk, ref)

    def test_empty_chunk(self):
        assert not gold_hit({"text": ""}, GoldChunkRef(doc="doc", snippet="x"))


class TestMatchRetrieved:
    def test_order_and_count(self):
        gold = [
            GoldChunkRef(doc="d1", snippet="按月领取基本养老金"),
            GoldChunkRef(doc="d2", snippet="缴费基数申报"),
        ]
        retrieved = [
            {"text": "缴费基数申报指南全文。", "metadata": {}},
            {"text": "按月领取基本养老金的条件。", "metadata": {}},
            {"text": "无关内容。", "metadata": {}},
        ]
        hits, matched = match_retrieved(retrieved, gold)
        assert hits == [True, True, False]
        assert matched == 2

    def test_single_chunk_covers_both(self):
        gold = [
            GoldChunkRef(doc="d1", snippet="按月领取基本养老金"),
            GoldChunkRef(doc="d2", snippet="累计缴费满十五年"),
        ]
        retrieved = [{"text": "累计缴费满十五年的，按月领取基本养老金。", "metadata": {}}]
        hits, matched = match_retrieved(retrieved, gold)
        assert hits == [True]
        assert matched == 2
