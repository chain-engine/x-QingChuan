"""晴川 RAG 评测（qingchuan-eval）

golden set 回归评测工具：以 JSONL 金标准数据集驱动，对运行中的 rag-service
（HTTP /api/v1/rag/retrieve、/api/v1/rag/query）做黑盒评测。

- 确定性指标（零 LLM 成本）：hit@k / MRR / context precision@k / recall / 答案 F1
- 双入口：CLI（qingchuan-eval）+ HTTP（qingchuan-eval-server）
- 为计划 C（RAGAS 深度评测）预留扩展位：--mode full 叠加生成侧指标，阈值门禁可配置
"""

__version__ = "0.1.0"

__all__ = [
    "client",
    "matcher",
    "metrics",
    "report",
    "runner",
    "schema",
]
