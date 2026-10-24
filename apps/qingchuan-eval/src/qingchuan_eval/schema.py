"""评测数据与配置 Schema（pydantic 单一事实来源）。

golden set 设计要点：
- 不写死运行时 document_id（上传时生成 UUID），金标准按「稳定文档键 + 片段文本」引用，
  检索命中按归一化文本包含匹配；chunk_index 仅作冻结 KB 状态下的精确引用（可选）。
- snippet 建议取自源文档的完整句子 / 短段落（约 20-120 字），保证可被单个 chunk 覆盖。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

EvalMode = Literal["retrieval", "full"]

# 默认聚合上报的 k 档位（hit@k / precision@k）
EVAL_TOP_KS: tuple[int, ...] = (1, 3, 5, 10)

DIFFICULTY_CHOICES = ("single_hop", "multi_hop", "boundary", "filtered")


class GoldChunkRef(BaseModel):
    """金标准片段引用（稳定键 + 文本；chunk_index 为可选精确引用）。"""

    doc: str = Field(default="", description="稳定文档键（源文件名 / 标题），当前为提示信息")
    snippet: str = Field(..., min_length=1, description="黄金片段文本，取自源文档原句")
    chunk_index: int | None = Field(default=None, description="可选：冻结 KB 状态下的片段索引")

    @field_validator("snippet")
    @classmethod
    def _snippet_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("snippet 不能为空白")
        return v


class GoldenSetEntry(BaseModel):
    """golden set 单条记录。"""

    id: str = Field(..., description="全局唯一 ID，如 pension-001")
    question: str = Field(..., min_length=1, description="评测问题")
    reference_answer: str | None = Field(default=None, description="标准答案（full 模式）")
    category: str = Field(default="general", description="业务分类，如 养老保险/医疗保险")
    difficulty: str = Field(
        default="single_hop", description="single_hop | multi_hop | boundary | filtered"
    )
    gold: list[GoldChunkRef] = Field(..., min_length=1, description="金标准片段引用列表")
    note: str | None = Field(default=None, description="备注（来源 / 年份口径等）")

    model_config = ConfigDict(extra="forbid")


class EvalConfig(BaseModel):
    """评测运行配置（阈值放配置不硬编码，为计划 C 门禁复用）。"""

    base_url: str = Field(default="http://127.0.0.1:8010", description="rag-service 地址")
    api_prefix: str = Field(default="/api/v1", description="HTTP API 前缀")
    top_k: int = Field(default=5, ge=1, le=20, description="检索返回数量（评估口径）")
    similarity_threshold: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="检索相似度阈值（评测建议 0.0；门禁在 threshold_*）",
    )
    use_mmr: bool = Field(default=False, description="是否启用 MMR 多样性重排")
    mmr_lambda: float = Field(default=0.5, ge=0.0, le=1.0)
    rrf_k: int | None = Field(
        default=None,
        ge=1,
        le=500,
        description="RRF 融合常数（None=服务端装配默认 60；网格调优时按组合传入）",
    )
    mode: EvalMode = Field(
        default="retrieval", description="retrieval=仅检索指标；full=叠加生成侧指标"
    )
    max_samples: int | None = Field(default=None, ge=1, description="最多评测条数（成本控制）")
    timeout: float = Field(default=30.0, gt=0, description="单次 HTTP 请求超时（秒）")
    # ── 回归门禁（计划 C 使用；未配置则只报告不判定）──
    threshold_hit_at_3: float | None = Field(
        default=None, ge=0.0, le=1.0, description="hit@3 门禁下限"
    )
    threshold_mrr: float | None = Field(default=None, ge=0.0, le=1.0, description="MRR 门禁下限")
    threshold_context_precision_at_3: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="context precision@3 门禁下限",
    )
    threshold_recall: float | None = Field(
        default=None, ge=0.0, le=1.0, description="context recall 门禁下限"
    )

    @property
    def retrieve_url(self) -> str:
        return f"{self.base_url}{self.api_prefix}/rag/retrieve"

    @property
    def query_url(self) -> str:
        return f"{self.base_url}{self.api_prefix}/rag/query"


class SampleResult(BaseModel):
    """单条样本评测结果。"""

    id: str
    question: str
    category: str
    difficulty: str
    hits: list[bool] = Field(default_factory=list, description="按检索顺序的 gold 命中标记")
    retrieved_count: int = 0
    matched_gold_count: int = 0
    gold_total: int = 0
    hit_at_3: float | None = None
    hit_at_5: float | None = None
    mrr: float | None = None
    precision_at_3: float | None = None
    recall: float | None = None
    recall_at_1: float | None = None
    recall_at_3: float | None = None
    recall_at_5: float | None = None
    recall_at_10: float | None = None
    # full 模式（生成侧）
    answer: str | None = None
    answer_containment: float | None = None
    answer_f1: float | None = None
    error: str | None = Field(default=None, description="该样本请求失败时记录错误")


class AggregateMetrics(BaseModel):
    """聚合指标（样本均值）。"""

    sample_count: int = 0
    hit_at_1: float | None = None
    hit_at_3: float | None = None
    hit_at_5: float | None = None
    hit_at_10: float | None = None
    mrr: float | None = None
    precision_at_1: float | None = None
    precision_at_3: float | None = None
    precision_at_5: float | None = None
    recall: float | None = None
    recall_at_1: float | None = None
    recall_at_3: float | None = None
    recall_at_5: float | None = None
    recall_at_10: float | None = None
    answer_containment: float | None = None
    answer_f1: float | None = None
    error_rate: float = 0.0


class ThresholdResult(BaseModel):
    """门禁判定结果（未配置阈值为 None）。"""

    metric: str
    threshold: float
    actual: float | None
    passed: bool | None = Field(default=None, description="未测到指标时为 None")


class EvalReport(BaseModel):
    """一次评测的完整报告（机器可读，供 CI / 错误分析消费）。"""

    generated_at: str
    config: EvalConfig
    aggregate: AggregateMetrics
    samples: list[SampleResult] = Field(default_factory=list)
    thresholds: list[ThresholdResult] = Field(default_factory=list)
    all_thresholds_passed: bool | None = None

    def write_json(self, path: str | Path) -> None:
        Path(path).write_text(self.model_dump_json(indent=2), encoding="utf-8")


# ── golden set 文件读写 ──────────────────────────────────────────


def load_golden_set(path: str | Path) -> list[GoldenSetEntry]:
    """读取 JSONL golden set，逐行校验；重复 id 报错。"""
    entries: list[GoldenSetEntry] = []
    seen: set[str] = set()
    p = Path(path)
    with p.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            raw: dict[str, Any] = __import__("json").loads(line)
            entry = GoldenSetEntry.model_validate(raw)
            if entry.id in seen:
                raise ValueError(f"{p}:{line_no} 重复的 golden id: {entry.id}")
            seen.add(entry.id)
            entries.append(entry)
    return entries


def save_golden_set(entries: list[GoldenSetEntry], path: str | Path) -> None:
    """写回 JSONL（UTF-8，逐行 JSON）。"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for entry in entries:
            f.write(entry.model_dump_json(exclude_none=True) + "\n")
