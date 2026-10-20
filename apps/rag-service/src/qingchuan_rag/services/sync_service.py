#!/usr/bin/env python3
"""人社数据同步服务：编排"拉取 → 转换 → 分块 → 向量化 → 入库"全流程。

与观海"直接上传"的差异点（晴川差异化核心）：
- 数据来源为人社系统离线数据（HRSSDataSourceClient 拉取），非用户上传；
- 提供周期调度（APScheduler，见 sync/scheduler.py）与 HTTP 触发接口
  （POST /api/v1/sync/trigger）两种触发渠道；
- 每次同步写入 sync_tasks 任务状态表（MySQL），并产生 sync_task 审计。

TODO(人社 API 接入后完善)：
    1. HRSSDataSourceClient.fetch_* 返回真实数据后，_convert_records
       需按人社字段映射为文档文本与元数据；
    2. 增量游标持久化（建议存 sync_tasks.extra）；
    3. 大批量场景改为分批事务提交 + 断点续跑。
"""

from __future__ import annotations

import threading
import uuid
from datetime import UTC, datetime
from typing import Any

from qingchuan_domain.schemas.sync import SyncTaskResult, SyncTaskStatus
from qingchuan_rag.core.config import settings
from qingchuan_rag.core.logger import logger
from qingchuan_rag.infras.database import get_session
from qingchuan_rag.infras.hrss import SOURCE_HRSS, HRSSDataSourceClient
from qingchuan_rag.repositories.sync_task_repository import SyncTaskRepository
from qingchuan_rag.services.audit_service import AuditService
from qingchuan_rag.services.base_service import BaseService
from qingchuan_rag.services.document_service import DocumentService
from qingchuan_rag.services.rag_service import RAGService

_INTERNAL_OPERATOR: dict[str, Any] = {
    "operator_id": "internal",
    "operator_name": "internal",
    "ip_address": None,
}


class SyncService(BaseService):
    """人社数据同步服务。"""

    entity_type = "sync_task"

    def __init__(
        self,
        document_service: DocumentService,
        rag_service: RAGService | None = None,
        audit_service: AuditService | None = None,
        client: HRSSDataSourceClient | None = None,
    ) -> None:
        self._doc_service = document_service
        self._rag_service = rag_service
        self._audit_service = audit_service
        self._client = client or HRSSDataSourceClient(
            base_url=settings.HRSS_API_URL,
            token=settings.HRSS_API_TOKEN,
            batch_size=settings.SYNC_BATCH_SIZE,
        )
        self._initialized = False
        self._running = False
        self._lock = threading.Lock()

    # ── 生命周期 ─────────────────────────────────────────
    def initialize(self) -> None:
        """初始化同步服务（依赖 document_service 已初始化）。"""
        self._initialized = True
        logger.info("SyncService initialized")

    def shutdown(self) -> None:
        """关闭同步服务。"""
        self._initialized = False
        logger.info("SyncService shut down")

    # ── 核心同步 ─────────────────────────────────────────
    def sync_once(
        self,
        full: bool = False,
        force: bool = False,
        channel: str = "manual",
    ) -> SyncTaskResult:
        """执行一次同步（拉取 → 转换 → 索引）。

        Args:
            full: True=全量同步；False=增量同步（默认）
            force: True=忽略已同步标记强制重跑（增量模式预留）
            channel: 触发渠道 manual / scheduler

        Returns:
            SyncTaskResult（任务状态、计数、消息）
        """
        if not self._initialized:
            raise RuntimeError("SyncService 未初始化，请先调用 initialize()")
        if not self._lock.acquire(blocking=False):
            return SyncTaskResult(
                task_id="",
                status="failed",
                channel=channel,
                full=full,
                message="已有同步任务正在执行，本次触发已跳过",
                error="sync_lock_busy",
                started_at=datetime.now(UTC),
                finished_at=datetime.now(UTC),
            )

        task_id = f"sync_{uuid.uuid4().hex[:12]}"
        started_at = datetime.now(UTC)
        result = SyncTaskResult(
            task_id=task_id,
            status="running",
            channel=channel,
            full=full,
            started_at=started_at,
            message="同步进行中",
        )
        try:
            self._save_task_started(result)
            logger.info(f"[{task_id}] 人社数据同步开始：channel={channel} full={full} force={force}")

            # 1. 拉取人社数据（full=True 全量；否则增量）
            records: list[dict[str, Any]] = []
            if full:
                records = self._client.fetch_full(batch_size=settings.SYNC_BATCH_SIZE)
            else:
                records = self._client.fetch_incremental(
                    since=self._last_sync_cursor(),
                    batch_size=settings.SYNC_BATCH_SIZE,
                )
            logger.info(f"[{task_id}] 拉取人社记录 {len(records)} 条")

            # 2. 逐条转换并索引入库（复用 DocumentService.upload_document）
            total = len(records)
            synced = 0
            failed = 0
            first_error: str | None = None
            for index, record in enumerate(records, start=1):
                try:
                    text = self._client._build_document_text(record)  # noqa: SLF001 - 骨架期直接复用
                    if not text.strip():
                        failed += 1
                        continue
                    metadata = self._client._build_document_metadata(record)  # noqa: SLF001
                    self._doc_service.upload_document(
                        text=text,
                        file_name=self._record_file_name(record, index),
                        file_type="txt",
                        file_size=len(text.encode("utf-8")),
                        metadata=metadata,
                        operator=_INTERNAL_OPERATOR,
                    )
                    synced += 1
                except Exception as exc:  # noqa: BLE001 - 单条失败不中断整批
                    failed += 1
                    first_error = first_error or str(exc)
                    logger.warning(f"[{task_id}] 记录 {index} 索引失败: {exc}")
                finally:
                    self._save_task_progress(
                        task_id=task_id,
                        total=total,
                        synced=synced,
                        failed=failed,
                    )

            finished_at = datetime.now(UTC)
            ok = failed == 0  # 无失败即成功（含 0 条数据：增量无新数据属正常）
            result = SyncTaskResult(
                task_id=task_id,
                status="success" if ok else "failed",
                channel=channel,
                full=full,
                total_records=total,
                synced_records=synced,
                failed_records=failed,
                started_at=started_at,
                finished_at=finished_at,
                message=f"同步完成：{synced} 成功 / {failed} 失败 / 共 {total} 条",
                error=first_error,
            )
            self._save_task_finished(result)
            logger.info(f"[{task_id}] 同步结束：{synced} 成功 / {failed} 失败 / 共 {total} 条")
            return result
        except Exception as exc:  # noqa: BLE001 - 同步主流程异常
            finished_at = datetime.now(UTC)
            result = SyncTaskResult(
                task_id=task_id,
                status="failed",
                channel=channel,
                full=full,
                started_at=started_at,
                finished_at=finished_at,
                message=f"同步异常终止：{exc}",
                error=str(exc),
            )
            self._save_task_finished(result)
            logger.error(f"[{task_id}] 同步异常终止: {exc}", exc_info=True)
            return result
        finally:
            self._lock.release()

    # ── 状态查询 ─────────────────────────────────────────
    def get_stats(self) -> dict[str, Any]:
        """获取同步服务统计（最近一次任务摘要）。"""
        latest = self.get_latest_status()
        return {
            "type": self.entity_type,
            "client_configured": bool(settings.HRSS_API_URL),
            "scheduler_enabled": settings.SYNC_ENABLED,
            "scheduler_cron": settings.SYNC_CRON,
            "latest": latest or {},
        }

    def get_status(self, task_id: str) -> dict[str, Any] | None:
        """按任务 ID 查询同步状态。"""
        session = get_session()
        try:
            repo = SyncTaskRepository(session=session)
            entity = repo.get_by_task_id(task_id)
            return self._to_dict(entity) if entity else None
        finally:
            session.close()

    def get_latest_status(self) -> dict[str, Any] | None:
        """查询最近一次同步任务状态。"""
        session = get_session()
        try:
            repo = SyncTaskRepository(session=session)
            rows = repo.get_latest(limit=1)
            return self._to_dict(rows[0]) if rows else None
        finally:
            session.close()

    # ── 内部工具 ─────────────────────────────────────────
    def _last_sync_cursor(self) -> datetime | None:
        """增量游标：最近一次成功任务的开始时间。

        TODO: 人社 API 接入后建议持久化数据源游标（存 sync_tasks.extra）。
        """
        session = get_session()
        try:
            repo = SyncTaskRepository(session=session)
            rows = repo.get_latest(limit=5)
            for row in rows:
                if row.status == "success" and row.started_at:
                    return row.started_at
            return None
        finally:
            session.close()

    def _save_task_started(self, status: SyncTaskStatus) -> None:
        """写入任务开始状态。"""
        session = get_session()
        try:
            repo = SyncTaskRepository(session=session)
            repo.create(
                task_id=status.task_id,
                status="running",
                channel=status.channel,
                full=status.full,
                source=SOURCE_HRSS,
                started_at=status.started_at,
            )
            repo.commit()
        except Exception as exc:  # noqa: BLE001 - 任务表写失败不阻断同步
            session.rollback()
            logger.warning(f"同步任务状态写入失败（started）: {exc}")
        finally:
            session.close()

    def _save_task_progress(
        self,
        *,
        task_id: str,
        total: int,
        synced: int,
        failed: int,
    ) -> None:
        """更新任务进度（低频调用，避免每记录一次会话开销）。"""
        session = get_session()
        try:
            repo = SyncTaskRepository(session=session)
            entity = repo.get_by_task_id(task_id)
            if entity:
                repo.update_status(
                    entity=entity,
                    status="running",
                    total_records=total,
                    synced_records=synced,
                    failed_records=failed,
                )
                repo.commit()
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            logger.warning(f"同步任务进度写入失败: {exc}")
        finally:
            session.close()

    def _save_task_finished(self, result: SyncTaskResult) -> None:
        """写入任务结束状态并记录审计。"""
        session = get_session()
        try:
            repo = SyncTaskRepository(session=session)
            entity = repo.get_by_task_id(result.task_id)
            if entity:
                repo.update_status(
                    entity=entity,
                    status=result.status,
                    total_records=result.total_records,
                    synced_records=result.synced_records,
                    failed_records=result.failed_records,
                    message=result.message,
                    error=result.error,
                    finished_at=result.finished_at,
                )
                repo.commit()
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            logger.warning(f"同步任务状态写入失败（finished）: {exc}")
        finally:
            session.close()
        if self._audit_service is not None:
            self._audit_service.log_event(
                entity_type=self.entity_type,
                entity_id=result.task_id,
                action="sync",
                operator=_INTERNAL_OPERATOR,
                after_data={
                    "status": result.status,
                    "channel": result.channel,
                    "full": result.full,
                    "total_records": result.total_records,
                    "synced_records": result.synced_records,
                    "failed_records": result.failed_records,
                    "message": result.message,
                },
                remarks=f"人社数据同步（{result.channel}）",
            )

    @staticmethod
    def _record_file_name(record: dict[str, Any], index: int) -> str:
        """构造同步文档文件名（便于文档列表溯源）。"""
        record_id = record.get("id") or record.get("record_id") or f"record_{index}"
        return f"hrss_{record_id}.txt"

    @staticmethod
    def _to_dict(entity: Any) -> dict[str, Any]:
        """实体 → 响应字典（时间转 ISO 字符串，保证 JSON 可序列化）。"""
        return {
            "task_id": entity.task_id,
            "status": entity.status,
            "channel": entity.channel,
            "full": entity.full,
            "source": entity.source,
            "total_records": entity.total_records,
            "synced_records": entity.synced_records,
            "failed_records": entity.failed_records,
            "message": entity.message,
            "error": entity.error,
            "started_at": entity.started_at.isoformat() if entity.started_at else None,
            "finished_at": entity.finished_at.isoformat() if entity.finished_at else None,
            "created_at": entity.created_at.isoformat() if entity.created_at else None,
        }


__all__ = ["SyncService"]
