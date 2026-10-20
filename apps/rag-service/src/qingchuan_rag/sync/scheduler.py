#!/usr/bin/env python3
"""人社数据同步周期调度器（APScheduler）。

- SYNC_ENABLED=true 时注册 cron 任务（默认每天 03:00，见 settings.SYNC_CRON）；
- 提供 trigger() 供 HTTP 触发接口 / CLI 复用同一执行入口；
- 调度器在应用 lifespan 中启动 / 关闭（见 main.py）。

TODO(接入人社 API 后)：
    1. 确认周期与业务窗口（默认 cron 表达式可在 config.yaml 覆盖）；
    2. 全量/增量策略：周期任务默认增量（full=False），
       首次部署可手动触发全量（POST /api/v1/sync/trigger {"full": true}）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from qingchuan_rag.core.logger import logger

if TYPE_CHECKING:  # 仅类型注解，避免 sync ↔ services 循环导入
    from qingchuan_rag.services.sync_service import SyncService

_JOB_ID: str = "hrss_sync_periodic"


class SyncScheduler:
    """人社数据同步周期调度器。"""

    def __init__(
        self,
        sync_service: SyncService,
        cron: str = "0 3 * * *",
        enabled: bool = False,
    ) -> None:
        self._sync_service = sync_service
        self._cron = cron
        self._enabled = enabled
        self._scheduler: BackgroundScheduler | None = None

    def start(self) -> None:
        """启动调度器（enabled=true 时注册 cron 任务）。"""
        if not self._enabled:
            logger.info("SYNC_ENABLED=false，人社同步周期调度未启动（可手动触发）")
            return
        self._scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
        self._scheduler.add_job(
            self.trigger,
            CronTrigger.from_crontab(self._cron, timezone="Asia/Shanghai"),
            id=_JOB_ID,
            name="人社数据周期同步",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        self._scheduler.start()
        logger.info(f"人社同步周期调度已启动：cron={self._cron}")

    def shutdown(self) -> None:
        """关闭调度器。"""
        if self._scheduler is not None:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
            logger.info("人社同步周期调度已关闭")

    def trigger(self, full: bool = False, force: bool = False) -> dict[str, Any]:
        """执行一次同步（调度任务 / 外部触发复用）。

        Returns:
            SyncTaskResult 的 model_dump（JSON 可序列化）。
        """
        result = self._sync_service.sync_once(full=full, force=force, channel="scheduler")
        return result.model_dump()


__all__ = ["SyncScheduler"]
