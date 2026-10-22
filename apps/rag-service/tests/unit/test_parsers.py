#!/usr/bin/env python3
"""infras/parsers.py 单元测试：文本解码 / PDF 文本提取 / 元数据规范化。"""

import pytest

from qingchuan_rag.core.exceptions import DocumentError
from qingchuan_rag.infras.parsers import (
    decode_text_content,
    extract_pdf_text,
    sanitize_metadata,
)


class TestDecodeTextContent:
    def test_utf8(self) -> None:
        assert decode_text_content("社保缴费基数申报".encode()) == "社保缴费基数申报"

    def test_gbk_fallback(self) -> None:
        assert decode_text_content("武汉市2025年指南".encode("gbk")) == "武汉市2025年指南"

    def test_ascii(self) -> None:
        assert decode_text_content(b"plain ascii") == "plain ascii"

    def test_binary_raises(self) -> None:
        with pytest.raises(DocumentError):
            decode_text_content(bytes(range(256)) * 4)


class TestExtractPdfText:
    def test_text_pdf(self) -> None:
        import pymupdf

        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((72, 100), "社保缴费基数申报测试文本 Hello PDF", fontname="china-s")
        pdf_bytes = doc.tobytes()
        text = extract_pdf_text(pdf_bytes)
        assert "社保缴费基数申报测试文本" in text
        assert "Hello PDF" in text

    def test_empty_pdf_raises(self) -> None:
        import pymupdf

        doc = pymupdf.open()
        doc.new_page()  # 空白页，无文本层
        with pytest.raises(DocumentError):
            extract_pdf_text(doc.tobytes())

    def test_invalid_bytes_raises(self) -> None:
        with pytest.raises(DocumentError):
            extract_pdf_text(b"not a pdf at all")


class TestSanitizeMetadata:
    def test_scalars_kept(self) -> None:
        meta = {"title": "指南", "year": 2025, "ratio": 1.5, "enabled": True}
        assert sanitize_metadata(meta) == meta

    def test_list_to_json_string(self) -> None:
        result = sanitize_metadata({"tags": ["社保", "缴费基数"]})
        assert result["tags"] == '["社保", "缴费基数"]'
        assert isinstance(result["tags"], str)

    def test_dict_to_json_string(self) -> None:
        result = sanitize_metadata({"dept": {"name": "武汉市人社局"}})
        assert result["dept"] == '{"name": "武汉市人社局"}'

    def test_none_to_empty_string(self) -> None:
        assert sanitize_metadata({"author": None}) == {"author": ""}

    def test_none_or_empty(self) -> None:
        assert sanitize_metadata(None) == {}
        assert sanitize_metadata({}) == {}
