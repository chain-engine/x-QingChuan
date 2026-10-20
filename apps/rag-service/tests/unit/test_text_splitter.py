#!/usr/bin/env python3
"""
文档切分（chunking）单元测试

覆盖：TextChunk 结构、BaseChunkingProvider 元数据行为、
get_chunking_provider 工厂与 LangChain provider（recursive）实际切分。
（旧 utils.text_splitter 已在 f5f956c 重构中迁移为 chunking 模块）
"""

import pytest

from qingchuan_rag.infras.chunking import (
    BaseChunkingProvider,
    LangchainProvider,
    TextChunk,
    get_chunking_provider,
    list_chunking_providers,
)


class TestTextChunk:
    """文本分块结构测试"""

    def test_basic_fields(self):
        chunk = TextChunk(content="hello", chunk_id="doc1_chunk_0")
        assert chunk.content == "hello"
        assert chunk.chunk_id == "doc1_chunk_0"
        assert chunk.start_index == 0
        assert chunk.end_index == 0
        assert chunk.metadata == {}

    def test_repr(self):
        chunk = TextChunk(content="hello", chunk_id="c1")
        assert "c1" in repr(chunk)
        assert "5" in repr(chunk)  # length=5


class TestChunkingProviderBase:
    """基类元数据切分行为（不依赖第三方库）"""

    class _FakeProvider(BaseChunkingProvider):
        name = "fake"
        description = "fake provider"

        def chunk_text(self, text, **kwargs):
            # 按空行切段
            return [seg for seg in text.split("\n\n") if seg.strip()]

    def test_chunk_text_with_metadata(self):
        provider = self._FakeProvider(chunk_size=100, chunk_overlap=0)
        chunks = provider.chunk_text_with_metadata(
            "第一段。\n\n第二段。", document_id="doc123", metadata={"source": "test"}
        )
        assert len(chunks) == 2
        assert chunks[0].chunk_id == "doc123_chunk_0"
        assert chunks[1].chunk_id == "doc123_chunk_1"
        assert chunks[0].metadata["chunk_index"] == 0
        assert chunks[0].metadata["chunk_count"] == 2
        assert chunks[0].metadata["source"] == "test"

    def test_empty_text(self):
        provider = self._FakeProvider()
        chunks = provider.chunk_text_with_metadata("", document_id="d")
        assert chunks == []

    def test_get_config(self):
        provider = self._FakeProvider(chunk_size=64, chunk_overlap=8, separators=["\n"])
        config = provider.get_config()
        assert config["chunk_size"] == 64
        assert config["chunk_overlap"] == 8
        assert config["separators"] == ["\n"]


class TestGetChunkingProvider:
    """工厂函数测试"""

    def test_get_langchain_provider(self):
        provider = get_chunking_provider("langchain", chunk_size=200, strategy="recursive")
        assert isinstance(provider, LangchainProvider)
        assert provider.chunk_size == 200

    def test_invalid_provider(self):
        with pytest.raises(ValueError):
            get_chunking_provider("unknown_provider")

    def test_list_providers(self):
        providers = list_chunking_providers()
        names = {p["name"] for p in providers}
        assert {"langchain", "llamaindex"} <= names


class TestLangchainProvider:
    """LangChain recursive 切分（依赖 langchain_text_splitters，已安装）"""

    def test_basic_split(self):
        provider = get_chunking_provider(
            "langchain", chunk_size=50, chunk_overlap=0, strategy="recursive"
        )
        text = "这是第一段内容，用于测试递归字符切分。\n\n这是第二段内容，独立成块。"
        chunks = provider.chunk_text(text)
        assert len(chunks) >= 1
        assert all(isinstance(c, str) and c for c in chunks)

    def test_empty_text(self):
        provider = get_chunking_provider("langchain", strategy="recursive")
        assert provider.chunk_text("") == []
        assert provider.chunk_text("   ") == []

    def test_with_metadata(self):
        provider = get_chunking_provider(
            "langchain", chunk_size=100, chunk_overlap=10, strategy="recursive"
        )
        chunks = provider.chunk_text_with_metadata(
            "第一句话。第二句话。第三句话。", document_id="doc_x"
        )
        assert len(chunks) >= 1
        assert chunks[0].chunk_id.startswith("doc_x_chunk_")
        assert chunks[0].metadata["chunk_index"] == 0
        assert chunks[0].metadata["chunk_count"] == len(chunks)
