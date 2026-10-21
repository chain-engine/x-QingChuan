#!/usr/bin/env python3
"""
Enums Module

项目全部枚举定义，统一按 (mark, desc) 二元组声明。

继承判断规则（依据 mark 的原生类型）：
    mark 为 int 的枚举（如 HTTP 状态码） → IntBaseEnum
    mark 为 str 的枚举（状态、类型、名称等） → StrBaseEnum
"""

from qingchuan_domain.constants.enums import HttpStatus
from qingchuan_rag.constants.base import StrBaseEnum

# ====================================
# 通用领域
# ====================================
# HttpStatus 单一事实来源在 qingchuan_domain.constants.enums（本文件顶部 re-export）


class HeaderType(StrBaseEnum):
    """HTTP 请求头类型枚举"""

    REQUEST_ID = "X-Request-ID", "请求ID"
    AUTHORIZATION = "Authorization", "授权令牌"
    CONTENT_TYPE = "Content-Type", "内容类型"


# ====================================
# RAG 领域
# ====================================


class DocStatus(StrBaseEnum):
    """文档状态枚举"""

    PENDING = "pending", "待处理"
    PROCESSING = "processing", "处理中"
    COMPLETED = "completed", "已完成"
    FAILED = "failed", "处理失败"
    DELETED = "deleted", "已删除"


class DocType(StrBaseEnum):
    """文档类型枚举"""

    TXT = "txt", "纯文本"
    MD = "md", "Markdown"
    PDF = "pdf", "PDF文档"
    DOCX = "docx", "Word文档"
    HTML = "html", "HTML网页"


class DistanceType(StrBaseEnum):
    """距离度量类型枚举"""

    COSINE = "cosine", "余弦距离"
    EUCLIDEAN = "euclidean", "欧氏距离"
    DOT = "dot", "点积"


class RerankingProviderName(StrBaseEnum):
    """排序 Provider 名称枚举"""

    MMR_RERANKER = "mmr_reranker", "MMR重排序"
    RRF_RERANKER = "rrf_reranker", "RRF重排序"
    SEMANTIC_RERANKER = "semantic_reranker", "语义重排序"
    SCORE_FILTER = "score_filter", "分数过滤"


class LLMProviderType(StrBaseEnum):
    """LLM 提供者类型枚举"""

    DEEPSEEK = "deepseek", "DeepSeek"
    DOUBAO = "doubao", "豆包"
    ALIYUN = "aliyun", "阿里云"
    MIMO = "mimo", "MIMO"
    MOCK = "mock", "模拟"


class IntentType(StrBaseEnum):
    """查询意图类型枚举"""

    FACTUAL = "factual", "事实型"
    OPINION = "opinion", "观点型"
    LIST = "list", "列表型"
    DEFINITION = "definition", "定义型"
    COMPARISON = "comparison", "比较型"
    CAUSAL = "causal", "因果型"
    HOWTO = "howto", "操作型"
    UNKNOWN = "unknown", "未知"


class EntityType(StrBaseEnum):
    """实体类型枚举"""

    PERSON = "PERSON", "人名"
    LOCATION = "LOCATION", "地名"
    ORGANIZATION = "ORG", "组织/公司"
    TIME = "TIME", "时间表达式"
    NUMBER = "NUMBER", "数字/金额"
    TECH = "TECH", "技术术语"
    PRODUCT = "PRODUCT", "产品名"
    UNKNOWN = "UNKNOWN", "未知"


__all__ = [
    "HttpStatus",
    "HeaderType",
    "DocStatus",
    "DocType",
    "DistanceType",
    "RerankingProviderName",
    "LLMProviderType",
    "IntentType",
    "EntityType",
]
