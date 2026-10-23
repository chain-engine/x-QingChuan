# 晴川 RAG 评测（qingchuan-eval）

golden set 回归评测工具：以 JSONL 金标准数据集驱动，对运行中的 rag-service
（HTTP `/api/v1/rag/retrieve`、`/api/v1/rag/query`）做**黑盒评测**。

- **确定性指标（零 LLM 成本）**：hit@1/3/5/10、MRR、context precision@k、context recall、答案包含率、字符级 F1
- **双入口**：CLI（`qingchuan-eval`）+ HTTP（`qingchuan-eval-server`）
- **为计划 C（RAGAS 深度评测）预留**：`--mode full` 叠加生成侧指标；`threshold_*` 门禁可配置；报告机器可读

## 为什么独立成包（与 rag-service 隔离）

- 评测依赖（后续 RAGAS 等）不进入 rag-service 生产依赖；
- 评测目标是**运行中的服务**（黑盒），测的是用户真实走到的链路，而非进程内实现；
- 与现有 monorepo 结构（`apps/*`）一致，`apps/*` 已注册为 workspace 成员。

## 快速开始

```bash
cd apps/qingchuan-eval
uv sync --package qingchuan-eval     # 仅安装本包（不拉 rag-service 的重依赖）

# 1) 校验 golden set
uv run qingchuan-eval validate

# 2) 运行检索侧评测（零成本，可进 CI）
uv run qingchuan-eval run \
  --base-url http://127.0.0.1:8010 \
  --mode retrieval \
  --output report.json

# 3) 叠加生成侧指标（受 max-samples 控制 LLM 用量）
uv run qingchuan-eval run --mode full --max-samples 20

# 4) HTTP 触发（供 CI / 面板）
uv run qingchuan-eval-server   # :8030
curl -X POST http://127.0.0.1:8030/eval/run \
  -H 'Content-Type: application/json' \
  -d '{"config": {"base_url": "http://127.0.0.1:8010", "max_samples": 20}}'
```

## golden set 格式（`data/golden_set.jsonl`）

```json
{
  "id": "pension-001",
  "question": "养老保险累计缴费满15年，退休后能否按月领取养老金？",
  "reference_answer": "……",
  "category": "养老保险",
  "difficulty": "single_hop",
  "gold": [
    {"doc": "武汉市2025年社保缴费基数申报指南.pdf", "snippet": "累计缴费满十五年的，按月领取基本养老金。"}
  ],
  "note": "来源：人社政策问答"
}
```

设计要点：

- **不写死运行时 document_id**（上传时生成 UUID），金标准用「稳定文档键 + 片段文本」引用，
  命中判定为**归一化文本包含匹配**（`matcher.py`）；
- `snippet` 建议取源文档完整句子 / 短段落（约 20-120 字），保证可被单个 chunk 覆盖；
- `chunk_index` 为可选精确引用（冻结 KB 状态时使用）；
- `difficulty`：`single_hop`（单跳事实）/ `multi_hop`（多跳）/ `boundary`（边界与否定）/ `filtered`（需要元数据过滤）。

## 指标口径

- `hit@k`：前 k 个检索结果中是否命中 gold（样本级 0/1，聚合取均值）
- `MRR`：首个命中位置的倒数
- `context precision@k`：前 k 个结果中 gold 命中比例
- `context recall`：被任一检索结果命中的 gold 片段数 / gold 片段总数
- 答案指标（full 模式）：归一化包含率 + 字符级 F1

## 门禁（计划 C 用）

```bash
uv run qingchuan-eval run \
  --threshold-hit-at-3 0.85 \
  --threshold-mrr 0.60 \
  --threshold-context-precision-at-3 0.60 \
  --threshold-recall 0.80
```

任一指标低于阈值 → CLI 退出码 1（可作 CI 门禁）；阈值不配置时仅报告不判定。
每次算法调整跑一次，对比基线报告即可做回归。

## 目录

```text
apps/qingchuan-eval/
├── src/qingchuan_eval/
│   ├── schema.py        # golden set / 配置 / 报告 Schema（单一事实来源）
│   ├── metrics.py       # 确定性指标
│   ├── matcher.py       # gold 命中判定（文本包含 + 可选 chunk_index）
│   ├── client.py        # rag-service HTTP 黑盒客户端
│   ├── runner.py        # 评测执行器 → EvalReport
│   ├── report.py        # 控制台摘要
│   ├── cli.py           # qingchuan-eval（run / validate）
│   └── http_server.py   # qingchuan-eval-server（POST /eval/run）
├── tests/               # 指标 / 匹配 / schema 单元测试
└── data/
    ├── golden_set.jsonl # 金标准数据集（持续增长）
    └── corpus/          # 语料源文件（人社政策 / 问答）
```
