# 可观测性（Observability）

x-QingChuan RAG 服务的可观测性采用 **Provider 插件化事件总线** 设计：

- 业务埋点只发**结构化事件**，不关心下游平台；
- 平台接入 = 实现 `ObservabilityProvider` 基类并注册，**埋点零改动**；
- 默认栈：**Langfuse 自托管**（Trace 可视化）+ **本地聚合器**（率/分布指标）；
- 业务零阻断：任何 Provider 异常只记 warn，绝不影响 RAG 主链路。

## 1. 五指标与数据来源

| 指标 | 事件 | 落地 |
| --- | --- | --- |
| 检索耗时 | `RetrievalPhaseEvent`（understand/candidate/rank_filter/total 四段） | Langfuse span metadata + 聚合器 P50/P95/P99 |
| 召回数 | `RetrievalPhaseEvent.candidates / retrieved` | 聚合器均值/直方图 + Langfuse metadata |
| 空召回率 | `RetrievalPhaseEvent.empty_reason`（no_candidate / filtered_out） | 聚合器 `empty_retrieval.rate` |
| 生成 tokens | `GenerationEvent.tokens`（usage_metadata / token_usage 兼容提取） | Langfuse `usage_details` + 聚合器 p95/均值 |
| 失败率 | `FailureEvent` + `RagQueryEvent.status=error` | 聚合器 `failures.rate` + Langfuse ERROR level |

## 2. 架构与事件流

```
业务代码（retrieval / rag / middleware）
        │  emit(Event)          ← 埋点只构造事件，零平台依赖
        ▼
ObservabilityManager（事件总线）
   ├─ 自动补齐 request_id（contextvar，middleware 注入）
   ├─ trace_sample_rate 采样（request_id 稳定哈希）
   ├─ mask_query 脱敏（可选）
   └─ 逐个分发，try/except 隔离
        ├─▶ AggregatorProvider  → 本地滚动窗口（1h / 24h）→ GET /obs/stats
        ├─▶ LoggingProvider    → JSON 日志兜底（永不缺席）
        └─▶ LangfuseProvider   → Langfuse 自托管（Trace/耗时/tokens 可视化）
```

### 事件契约

| 事件 | 关键字段 | 触发点 |
| --- | --- | --- |
| `RetrievalPhaseEvent` | stage, latency_ms, candidates, retrieved, empty_reason | 检索管线三阶段 + total |
| `GenerationEvent` | tokens, model, latency_ms | 生成完成（含空召回兜底） |
| `RagQueryEvent` | query, query_len, top_k, latencies{trees}, tokens, provider, model, status, error_type | RAG 全链路收尾（ok/empty/error） |
| `HttpRequestEvent` | endpoint, status_class, latency_ms | HTTP 中间件（每请求） |
| `FailureEvent` | phase, error_type, message | 检索/生成异常路径 |

`request_id` 由 Manager 从 contextvar 自动补齐（HTTP 场景来自 middleware；CLI/离线为 None）。

## 3. 配置

### config.yaml

```yaml
observability:
  enabled: true
  providers: ["langfuse"]        # 可扩展：["langfuse", "prometheus", ...]
  trace_sample_rate: 1.0         # 1.0=全量；0.5=按 request_id 稳定哈希采样一半
  mask_query: false              # true 时写入 Langfuse 的 query 脱敏为 "[masked]"
  langfuse_host: http://localhost:3000
  langfuse_public_key: pk-local-qingchuan
  langfuse_secret_key: sk-local-qingchuan
```

### 环境变量

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `OBSERVABILITY_ENABLED` | `true` | 总开关（false 时零开销） |
| `OBSERVABILITY_PROVIDERS` | `["langfuse"]` | 平台列表 |
| `OBSERVABILITY_TRACE_SAMPLE_RATE` | `1.0` | 采样率（全量） |
| `OBSERVABILITY_MASK_QUERY` | `false` | 查询脱敏 |
| `LANGFUSE_HOST` | `http://localhost:3000` | 自托管地址 |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | 空 | 项目凭据（未配置时 LangfuseProvider 跳过，服务正常起） |

## 4. Langfuse 自托管部署

```bash
cd apps/rag-service/deploy/langfuse
cp .env.example .env          # 首次；生产环境必须更换所有默认密钥
docker compose --env-file .env up -d
# 等待 web 健康后访问 http://localhost:3000
# 首次启动自动创建管理员账号 + 项目（凭据见 .env LANGFUSE_INIT_*）
```

- 栈：`web + worker + postgres + clickhouse + redis`（官方社区版镜像 `langfuse/langfuse:3`）；
- 项目凭据默认 `pk-local-qingchuan` / `sk-local-qingchuan`，与上面 config 默认值一致；
- SDK 已固定 `langfuse>=2.55`（当前解析到 5.x，OTel 架构；Provider 已按 5.x 真实 API 适配）。

### 冒烟验证

```bash
# 1. 服务侧
uv run qingchuan-rag-api            # 启动（:8010）
curl http://localhost:8010/obs/stats   # 本地聚合快照

# 2. 触发一次查询
curl -X POST http://localhost:8010/api/v1/rag/query \
  -H 'Content-Type: application/json' \
  -d '{"query": "退休金如何计算"}'

# 3. Langfuse 侧：打开 http://localhost:3000 → Traces，应看到名为 rag_query 的 Trace，
#    内含 retrieval（retriever）与 generation 两个 span 及真实 token 用量。
```

## 5. 扩展新平台（如 Prometheus / 云厂商）

```python
# core/observability/providers/my_provider.py
from qingchuan_rag.core.observability.base import ObservabilityProvider


class MyProvider(ObservabilityProvider):
    name = "my_platform"

    def initialize(self) -> None:
        # 可选：连接/认证；失败抛异常由 Manager 捕获跳过
        ...

    def handle_event(self, event) -> None:
        # 把事件翻译成自身形态；实现必须不抛异常
        ...

    def shutdown(self) -> None: ...
```

然后在 `core/observability/manager.py` 的 `initialize()` 循环中按 `name` 注册，
并在 `config.observability.providers` 列表中加入名称。**埋点代码零改动。**

## 6. 本地指标端点（GET /obs/stats）

聚合器滚动窗口（1h `window_3600s` / 24h `window_86400s`）返回：

- `retrieval_latency_ms`: p50/p95/p99/count
- `retrieved_docs`: mean / histogram
- `empty_retrieval`: total / rate / reasons
- `generation_tokens`: prompt/completion p95 与均值
- `failures`: total / by_phase / rate
- `http_5xx_rate`

## 7. 注意事项

- **采样与脱敏**：默认全量采样（1.0）、不脱敏；人社数据敏感场景建议评估 `mask_query=true`
  与适当降采样（0.1~0.5）后再上生产；
- **Langfuse 数据留存**：自托管 ClickHouse 存储，需要按数据量规划保留策略与备份；
- **CLI/离线模式**：不经过 lifespan，Manager 未初始化（enabled=False），埋点零开销。

## 8. 端到端验证结论（v4 实时查询层）

- **trace id 约束**：Langfuse trace id 必须是 32 位小写 hex；`LangfuseProvider._trace_id()`
  对合法 rid 原样透传，非法（如 `smoke-xxx`、大写）稳定映射为 md5，保证幂等可重放；
- **v4 实时路径**：SDK 5.x 走 OTLP（`POST /api/public/otel/v1/traces`，带
  `x-langfuse-ingestion-version: 4`），事件实时写入 ClickHouse `events_core` + MinIO blob；
  **UI 与 v2 API（`GET /api/public/v2/observations`、`/v2/metrics`）直接查询 events_core**——
  OTLP 数据即写即见，不需要等待 worker 传播；
- **v3 兼容层说明**：`observations`/`traces`/`analytics_*` 表由 legacy ingestion（
  `POST /api/public/ingestion`）与 blob 传播填充；v3 端点 `GET /api/public/traces`
  查不到 OTLP 数据属正常，不代表丢失（数据在 events_core，UI 用 v2 API）；
- **`LANGFUSE_MIGRATION_V4_WRITE_MODE=dual`**（web+worker 共享）：保持 legacy ingestion
  兼容（旧 SDK/第三方集成可写入）。worker 日志 `[DUAL WRITE] No partitions available`
  是 events_only/dual 下无 v3 兼容数据待传播的提示，不影响 OTLP 实时链路；生产如确认
  所有客户端均走 OTLP，可改回 `events_only` 降低后台负载；
- **验证记录**：`uv run pytest tests -q -x` 全量通过；`tmp_obs_e2e.py` 真实发出
  rag_query/retrieval/generation 三个 span，v2 API 查询确认可见（含采样/脱敏/trace id 兜底）。

