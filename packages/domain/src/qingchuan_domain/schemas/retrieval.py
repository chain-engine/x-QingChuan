"""共享领域协议层：检索请求 / 响应的数据契约（跨服务单一事实来源）。

rag-service 的 HTTP/MCP 接入层 DTO（schemas/rag.py）与本协议字段对齐；
agent-service 等下游通过本协议消费检索结果，不感知向量库实现。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class RetrievalQuery(BaseModel):
    """检索请求（领域协议）。"""

    query: str = Field(min_length=1, max_length=2000, description="查询语句")
    top_k: int = Field(default=5, ge=1, le=50, description="返回片段数量上限")
    similarity_threshold: float | None = Field(
        default=None, ge=0.0, le=1.0, description="相似度阈值，低于该值的片段被过滤"
    )
    use_mmr: bool = Field(default=False, description="是否启用 MMR 多样性重排")
    mmr_lambda: float = Field(
        default=0.5, ge=0.0, le=1.0, description="MMR 参数，0=多样性优先，1=相关性优先"
    )
    metadata_filter: dict[str, Any] | None = Field(
        default=None, description='元数据过滤条件，如 {"source_type": "policy"}'
    )
    scope: str | None = Field(default=None, description="检索范围标识（如参保人/政策），预留")


class RetrievedChunk(BaseModel):
    """检索命中的文档片段（领域协议）。

    text 为主字段（与观海检索结果结构一致）；content 仅为兼容早期骨架
    调用的别名输入，构造时自动同步到 text。
    """

    chunk_id: str = Field(description="片段唯一 ID")
    document_id: str = Field(default="", description="所属文档 ID")
    source: str = Field(default="", description="来源标识（如 hrss/upload）")
    text: str = Field(default="", description="片段文本")
    content: str = Field(default="", description="兼容字段：构造时同步为 text 的别名")
    score: float = Field(default=0.0, ge=0.0, le=1.0, description="相关性分数")
    metadata: dict[str, Any] = Field(default_factory=dict, description="片段元数据")

    @model_validator(mode="before")
    @classmethod
    def _alias_content(cls, data: Any) -> Any:
        """兼容早期骨架：仅提供 content 时自动映射到 text。"""
        if isinstance(data, dict) and "content" in data and "text" not in data:
            return {**data, "text": data["content"]}
        return data


class RetrievalResponse(BaseModel):
    """检索响应（领域协议）。"""

    query: str = Field(default="", description="原始查询语句")
    chunks: list[RetrievedChunk] = Field(default_factory=list, description="命中的片段列表")
    total: int = Field(default=0, description="命中片段总数")


__all__ = ["RetrievalQuery", "RetrievalResponse", "RetrievedChunk"]
