#!/usr/bin/env python3
"""
文件内容解析层（infras/parsers.py）

职责：
- 文本类文件：字节 → 字符串（utf-8 优先，gbk 兜底）
- PDF 文件：字节 → 文本（PyMuPDF 提取；扫描件/图片型 PDF 无文本层时明确报错）
- 元数据规范化：Chroma 只接受 str/int/float/bool 标量，list/dict 等结构化为 JSON 字符串

与上层关系：http_server/v1/document.py 按文件类型分流调用；document_service
入库前对 metadata 做规范化，保证向量索引与检索过滤可用。
"""

from __future__ import annotations

import json
from typing import Any

import pymupdf

from qingchuan_rag.core.exceptions import DocumentError

_TEXT_ENCODINGS = ("utf-8", "gbk")


def decode_text_content(content: bytes) -> str:
    """将文本类文件字节解码为字符串（utf-8 优先，gbk 兜底）。"""
    for encoding in _TEXT_ENCODINGS:
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise DocumentError(
        "Unsupported file encoding: 文件文本编码无法识别（utf-8 / gbk 均解码失败），"
        "请转存为 UTF-8 编码的文本文件"
    )


def extract_pdf_text(content: bytes) -> str:
    """从 PDF 字节中提取文本（仅限带文本层的 PDF）。

    Raises:
        DocumentError: PDF 解析失败，或无文本层（扫描件/图片型 PDF）。
    """
    try:
        with pymupdf.open(stream=content, filetype="pdf") as doc:
            pages = [page.get_text("text", sort=True) for page in doc]
    except Exception as e:  # noqa: BLE001 - 统一转为业务错误
        raise DocumentError(f"PDF 解析失败: {e}") from e

    text = "\n\n".join(page.strip() for page in pages if page.strip())
    if not text:
        raise DocumentError("PDF 无可提取的文本：疑似扫描件/图片型 PDF，请先转为文本或做 OCR")
    return text


def sanitize_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    """规范化元数据值，保证 Chroma 可存储（str/int/float/bool）。

    list / dict / None 等结构：None 转空串，其余 JSON 序列化为字符串，
    避免向量索引写入时报错，同时保留检索过滤时的原始语义。
    """
    if not metadata:
        return {}
    normalized: dict[str, Any] = {}
    for key, value in metadata.items():
        if value is None:
            normalized[key] = ""
        elif isinstance(value, (str, int, float, bool)):
            normalized[key] = value
        else:
            normalized[key] = json.dumps(value, ensure_ascii=False)
    return normalized
