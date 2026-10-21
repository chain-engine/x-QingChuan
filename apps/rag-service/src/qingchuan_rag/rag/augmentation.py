#!/usr/bin/env python3
"""
Augmentation Module

增强模块 - RAG中负责将检索结果与查询进行增强融合的环节
"""

import re
from typing import Any

from qingchuan_rag.constants import DEFAULT_SYSTEM_PROMPT, DEFAULT_USER_PROMPT_TEMPLATE
from qingchuan_rag.core.logger import logger

# 中文停用词集合（常见的无意义词汇，压缩时不作为关键词）
STOPWORDS = {
    "的",
    "了",
    "在",
    "是",
    "我",
    "有",
    "和",
    "就",
    "不",
    "人",
    "都",
    "一",
    "一个",
    "上",
    "也",
    "很",
    "到",
    "说",
    "要",
    "去",
    "你",
    "会",
    "着",
    "没有",
    "看",
    "好",
    "自己",
    "这",
    "那",
    "他",
    "她",
    "它",
    "们",
    "这个",
    "那个",
    "什么",
    "怎么",
    "为什么",
    "如何",
    "可以",
    "能",
    "应该",
    "可能",
    "需要",
    "为了",
    "因为",
    "所以",
    "但是",
    "如果",
    "虽然",
    "还是",
    "或者",
    "而且",
    "以及",
    "关于",
    "通过",
    "对于",
}


class Augmentation:
    """增强器"""

    def __init__(
        self,
        system_prompt: str | None = None,
        user_prompt_template: str | None = None,
        max_context_length: int = 8000,
    ):
        self._system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
        self._user_prompt_template = user_prompt_template or DEFAULT_USER_PROMPT_TEMPLATE
        self._max_context_length = max_context_length

    def initialize(self) -> None:
        """初始化增强器（无需加载资源，保持接口一致性）"""
        pass

    def shutdown(self) -> None:
        """关闭增强器（无需加载资源，保持接口一致性）"""
        pass

    @staticmethod
    def clean_context(text: str) -> str:
        """01 上下文清洗：移除多余空白、特殊字符"""
        # 合并连续空白
        text = re.sub(r"[ \t]+", " ", text)
        # 移除行首行尾空白
        text = "\n".join(line.strip() for line in text.split("\n"))
        # 移除连续空行
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def compress_context(
        text: str,
        query_keywords: set[str],
        max_length: int,
    ) -> str:
        """02 上下文压缩：基于关键词保留高相关性句子"""
        if not query_keywords:
            return Augmentation.smart_truncate(text, max_length)

        sentences = [s.strip() for s in re.split(r"[。！？\n]+", text) if s.strip()]
        if not sentences:
            return text

        # 计算每个句子的关键词匹配分数
        scored_sentences = []
        for sent in sentences:
            sent_lower = sent.lower()
            keyword_hits = sum(1 for kw in query_keywords if kw in sent_lower)
            density = keyword_hits / max(len(sent), 1)
            score = keyword_hits * 0.7 + density * 0.3 * len(query_keywords)
            scored_sentences.append((score, sent))

        # 优先保留高匹配句子
        scored_sentences.sort(key=lambda x: -x[0])

        result_sentences = []
        total_len = 0

        for _, sent in scored_sentences:
            if total_len + len(sent) + 1 > max_length:
                remaining = max_length - total_len - 1
                if remaining > 50:
                    result_sentences.append(Augmentation.smart_truncate(sent, remaining))
                    total_len += len(result_sentences[-1]) + 1
                break
            result_sentences.append(sent)
            total_len += len(sent) + 1

        # 按原文顺序重组
        original_order = {s: i for i, s in enumerate(sentences)}
        result_sentences.sort(key=lambda s: original_order[s])

        return "".join(result_sentences)

    @staticmethod
    def format_context(doc: dict[str, Any], index: int, include_metadata: bool = False) -> str:
        """03 上下文格式化：添加文档标签和来源信息"""
        text = doc.get("text", "")
        if include_metadata:
            metadata = doc.get("metadata", {})
            source = metadata.get("source", "unknown")
            return f"[文档{index + 1}] 来源: {source}\n{text}"
        return f"[文档{index + 1}]\n{text}"

    @staticmethod
    def smart_truncate(text: str, max_length: int) -> str:
        """智能截断：在句子边界处截断"""
        if len(text) <= max_length:
            return text

        truncated = text[:max_length]
        matches = list(re.finditer(r"[。！？\n]", truncated))

        if matches:
            last_punct = matches[-1]
            return truncated[: last_punct.end()] + "..."

        space_match = list(re.finditer(r"\s", truncated[::-1]))
        if space_match:
            last_space_pos = max_length - space_match[0].start()
            return truncated[:last_space_pos] + "..."

        return truncated + "..."

    def _extract_query_keywords(self, query: str) -> set[str]:
        """从查询中提取关键词"""
        words = re.split(r"[\s,，、。！？；;]+", query.lower())
        return {w for w in words if w and w not in STOPWORDS and len(w) > 1}

    def augment(
        self,
        query: str,
        retrieved_docs: list[dict[str, Any]],
        include_metadata: bool = False,
    ) -> dict[str, Any]:
        """增强查询与检索结果"""
        if not retrieved_docs:
            return {
                "system_prompt": self._system_prompt,
                "user_prompt": query,
                "full_prompt": query,
                "context_count": 0,
                "context_length": 0,
            }

        # 预处理：提取查询关键词
        query_keywords = self._extract_query_keywords(query)
        logger.debug(f"提取到查询关键词: {query_keywords}")

        # 计算每个文档的长度配额
        per_doc_quota = self._max_context_length // len(retrieved_docs)

        context_items = []
        total_length = 0

        for i, doc in enumerate(retrieved_docs):
            # 01 上下文清洗
            original_text = doc.get("text", "")
            cleaned_text = self.clean_context(original_text)

            # 02 上下文压缩
            compressed_text = self.compress_context(
                text=cleaned_text,
                query_keywords=query_keywords,
                max_length=per_doc_quota,
            )

            text_len = len(compressed_text)

            # 检查总长度
            if total_length + text_len > self._max_context_length:
                remaining = self._max_context_length - total_length
                if remaining > 100:
                    compressed_text = self.smart_truncate(compressed_text, remaining)
                    text_len = len(compressed_text)
                else:
                    break

            total_length += text_len

            # 03 上下文格式化
            context_items.append(
                self.format_context({**doc, "text": compressed_text}, i, include_metadata)
            )

            if total_length >= self._max_context_length:
                break

        # 04 Prompt 构造&上下文拼接
        context_text = "\n\n".join(context_items)
        user_prompt = self._user_prompt_template.format(
            context=context_text,
            query=query,
        )

        return {
            "system_prompt": self._system_prompt,
            "user_prompt": user_prompt,
            "full_prompt": user_prompt,
            "context_count": len(context_items),
            "context_length": total_length,
        }

    def build_prompt(self, query: str, contexts: list[str]) -> str:
        """构建带有上下文的prompt

        Args:
            query: 用户查询
            contexts: 上下文字符串列表

        Returns:
            增强后的完整prompt
        """
        if not contexts:
            return query

        context_text = "\n\n".join([f"[文档{i + 1}]\n{ctx}" for i, ctx in enumerate(contexts)])
        return self._user_prompt_template.format(
            context=context_text,
            query=query,
        )
