"""Chunking 策略单元测试：LangChain（recursive/character/token/semantic）与 LlamaIndex（sentence/token/semantic/markdown）。

semantic 策略使用确定性 Mock embeddings 验证断点逻辑（不加载真实模型）；
缺省 embeddings 的懒加载路径仅验证"构造不触发模型加载"。
"""

from __future__ import annotations

import pytest

from qingchuan_rag.infras.chunking import (
    LangchainProvider,
    LlamaIndexProvider,
    SemanticSplitter,
    get_chunking_provider,
)

SAMPLE_TEXT = (
    "晴川项目是面向人社场景的检索增强生成系统。它包含离线数据同步、"
    "语义检索与生成问答三大能力。数据从人社 API 拉取后进入向量库。"
    "完全不相关话题。这条句子与前后的主题都不一致。"
    "检索阶段采用多路召回与重排。BM25 负责稀疏检索。向量检索负责稠密召回。"
    "生成阶段由大模型基于检索结果作答。回答会附带引用来源。"
)


class MockEmbeddings:
    """确定性向量：含"不相关"的句段用正交向量（与上下文相似度 0），其余同向（相似度 1）。

    配合 SemanticSplitter 的 percentile 断点：第 4 句与前后都不相似，
    预期断在其前后，切成 3 个语义组。
    """

    def encode(self, texts: list[str], normalize: bool = True) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] if "不相关" not in t else [0.0, 1.0, 0.0] for t in texts]


class TestLangchainProvider:
    @pytest.mark.parametrize("strategy", ["recursive", "character", "token"])
    def test_basic_strategies(self, strategy: str) -> None:
        provider = LangchainProvider(chunk_size=120, chunk_overlap=10, strategy=strategy)
        chunks = provider.chunk_text(SAMPLE_TEXT)
        min_chunks = 1 if strategy == "character" else 2  # character 按 \n 切，无换行时 1 块合法
        assert len(chunks) >= min_chunks
        assert all(c and c.strip() for c in chunks)

    def test_recursive_reconstructs_text(self) -> None:
        provider = LangchainProvider(chunk_size=120, chunk_overlap=0, strategy="recursive")
        chunks = provider.chunk_text(SAMPLE_TEXT)
        assert "".join(chunks).replace(" ", "") == SAMPLE_TEXT.replace(" ", "")

    def test_semantic_breakpoints(self) -> None:
        # percentile=95 在样本过少时接近最大值、无断点（算法固有行为，生产长文本
        # 距离分布广则正常）；此处用 70 分位验证断点机制本身。
        provider = LangchainProvider(
            chunk_size=1000,
            chunk_overlap=0,
            strategy="semantic",
            embeddings=MockEmbeddings(),
            breakpoint_threshold_amount=70,
        )
        chunks = provider.chunk_text(SAMPLE_TEXT)
        assert len(chunks) == 3
        assert "完全不相关话题。" in chunks[1]

    def test_semantic_metadata_offsets_match_source(self) -> None:
        provider = LangchainProvider(
            chunk_size=1000,
            chunk_overlap=0,
            strategy="semantic",
            embeddings=MockEmbeddings(),
            breakpoint_threshold_amount=70,
        )
        chunks = provider.chunk_text_with_metadata(SAMPLE_TEXT, document_id="doc-1")
        assert len(chunks) == 3
        for tc in chunks:
            assert tc.start_index >= 0 and tc.end_index > tc.start_index
            # 语义切分保留标点，chunk 应为原文连续子串，start/end 可直接定位
            assert SAMPLE_TEXT[tc.start_index : tc.end_index] == tc.content

    def test_unsupported_strategy_raises(self) -> None:
        provider = LangchainProvider(strategy="nonexistent")
        with pytest.raises(ValueError, match="不支持的切分策略"):
            provider.chunk_text(SAMPLE_TEXT)

    def test_empty_text(self) -> None:
        provider = LangchainProvider(strategy="semantic", embeddings=MockEmbeddings())
        assert provider.chunk_text("") == []
        assert provider.chunk_text("   ") == []


class TestSemanticSplitter:
    def test_lazy_embeddings_not_loaded_on_construction(self) -> None:
        splitter = SemanticSplitter(chunk_size=120)
        assert splitter._model is None  # 构造不触发模型加载

    def test_no_punctuation_hard_splits_oversized_text(self) -> None:
        long_text = "无标点连续文本" * 300
        splitter = SemanticSplitter(chunk_size=120)
        chunks = splitter.split_text(long_text)
        assert all(len(c) <= 120 for c in chunks)


class TestLlamaIndexProvider:
    @pytest.mark.parametrize("strategy", ["sentence", "token", "semantic", "markdown"])
    def test_all_strategies(self, strategy: str) -> None:
        provider = LlamaIndexProvider(chunk_size=120, chunk_overlap=10, strategy=strategy)
        chunks = provider.chunk_text(SAMPLE_TEXT)
        assert len(chunks) >= 1
        assert all(c and c.strip() for c in chunks)


class TestFactory:
    def test_get_provider(self) -> None:
        provider = get_chunking_provider("llamaindex", chunk_size=80, strategy="sentence")
        chunks = provider.chunk_text(SAMPLE_TEXT)
        assert len(chunks) >= 1

    def test_unknown_provider_raises(self) -> None:
        with pytest.raises(ValueError, match="不支持的切分提供者"):
            get_chunking_provider("unknown")
