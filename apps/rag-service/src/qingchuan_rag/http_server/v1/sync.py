#!/usr/bin/env python3
"""人社数据同步触发接口（晴川差异化能力）。

与"直接上传"模式的差异：晴川知识库数据由人社系统离线同步进入，
本模块提供：
- POST /sync/trigger   触发一次同步（full=全量 / force=强制重跑）
- GET  /sync/status    最近一次同步任务状态
- GET  /sync/status/{task_id}  指定任务状态

周期调度由 SyncScheduler（APScheduler）承担，SYNC_ENABLED=true 生效；
本接口适用于人工补跑 / 首次全量 / 外部编排触发。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, Request

from qingchuan_domain.schemas.sync import SyncTriggerRequest
from qingchuan_rag.core.logger import logger
from qingchuan_rag.http_server.dependencies import get_sync_service
from qingchuan_rag.http_server.response import success_response
from qingchuan_rag.schemas.responses import ResponseModel
from qingchuan_rag.services.sync_service import SyncService

router = APIRouter(prefix="/sync", tags=["人社同步"])


@router.post(
    "/trigger",
    summary="触发人社数据同步",
    description="触发一次人社系统离线数据到向量库的同步（默认增量；full=true 全量）",
    response_model=ResponseModel,
)
def trigger_sync(
    request: Request,
    body: SyncTriggerRequest | None = None,
    sync_service: SyncService = Depends(get_sync_service),
) -> dict[str, Any]:
    """触发一次同步（手动渠道）。"""
    try:
        payload = body or SyncTriggerRequest()
        result = sync_service.sync_once(
            full=payload.full,
            force=payload.force,
            channel="manual",
        )
        return success_response(
            data=result.model_dump(),
            request=request,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(f"触发人社同步失败: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.get(
    "/status",
    summary="最近同步状态",
    description="查询最近一次人社数据同步任务状态",
    response_model=ResponseModel,
)
def get_latest_status(
    request: Request,
    sync_service: SyncService = Depends(get_sync_service),
) -> dict[str, Any]:
    """最近一次同步状态。"""
    status = sync_service.get_latest_status()
    if status is None:
        raise HTTPException(status_code=404, detail="暂无同步任务记录")
    return success_response(data=status, request=request)


@router.get(
    "/status/{task_id}",
    summary="同步任务状态",
    description="按任务 ID 查询同步状态",
    response_model=ResponseModel,
)
def get_task_status(
    request: Request,
    task_id: str = Path(description="同步任务 ID，如 sync_xxxxxxxxxxxx"),
    sync_service: SyncService = Depends(get_sync_service),
) -> dict[str, Any]:
    """指定任务同步状态。"""
    status = sync_service.get_status(task_id)
    if status is None:
        raise HTTPException(status_code=404, detail="同步任务不存在")
    return success_response(data=status, request=request)


__all__ = ["router"]
