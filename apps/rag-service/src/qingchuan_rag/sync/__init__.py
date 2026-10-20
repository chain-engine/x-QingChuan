"""人社数据同步模块。

- scheduler.py：APScheduler 周期调度器（SYNC_ENABLED=true 时注册 cron 任务）
- services/sync_service.py：同步编排（拉取 → 清洗 → 分块 → 向量化 → 入库）
- 数据源接口层在 infras/hrss.py（依赖 infras/http.py 的 HTTP 请求能力）

与观海"直接上传"的差异：晴川知识库数据由人社系统离线同步进入，
触发渠道包括外部 HTTP 触发接口（POST /api/v1/sync/trigger）与内置周期调度。
"""

from qingchuan_rag.sync.scheduler import SyncScheduler

__all__ = ["SyncScheduler"]
