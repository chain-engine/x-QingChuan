#!/usr/bin/env python3
"""业务审计日志查询接口（内部管理面）。

内部管理只读接口：
- 列表：按实体类型 / 操作 / 操作者 / 关键字 / 时间范围分页搜索；
- 详情：单条审计记录。

审计记录由 services 层业务方法内写入（DocumentService / RAGService /
SyncService），本接口只读查询，不产生新审计。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from qingchuan_rag.core.logger import logger
from qingchuan_rag.http_server.dependencies import get_audit_service
from qingchuan_rag.http_server.response import success_response
from qingchuan_rag.schemas.responses import ResponseModel
from qingchuan_rag.services.audit_service import AuditService

router = APIRouter(prefix="/audit", tags=["审计"])


@router.get(
    "/logs",
    summary="审计日志列表",
    description="按条件分页查询业务审计日志",
    response_model=ResponseModel,
)
def list_audit_logs(
    request: Request,
    entity_type: str | None = Query(
        default=None, description="实体类型过滤，如 document/rag_query/sync_task"
    ),
    action: str | None = Query(default=None, description="操作类型过滤，如 upload/delete/sync"),
    operator_id: str | None = Query(default=None, description="操作者过滤"),
    start_time: datetime | None = Query(default=None, description="开始时间（ISO 格式）"),
    end_time: datetime | None = Query(default=None, description="结束时间（ISO 格式）"),
    keyword: str | None = Query(
        default=None, description="关键字（模糊匹配实体类型/操作/实体ID/操作者/IP/备注）"
    ),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页记录数"),
    service: AuditService = Depends(get_audit_service),
) -> dict[str, Any]:
    """审计日志列表接口。"""
    try:
        result = service.search(
            entity_type=entity_type,
            action=action,
            operator_id=operator_id,
            start_time=start_time,
            end_time=end_time,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
        return success_response(data=result, request=request)
    except Exception as e:
        logger.error(f"查询审计日志失败: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get(
    "/logs/{log_id}",
    summary="审计日志详情",
    description="按 ID 查询单条审计记录",
    response_model=ResponseModel,
)
def get_audit_log(
    request: Request,
    log_id: int,
    service: AuditService = Depends(get_audit_service),
) -> dict[str, Any]:
    """审计日志详情接口。"""
    try:
        detail = service.get_by_id(log_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="审计记录不存在")
        return success_response(data=detail, request=request)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询审计日志详情失败: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


__all__ = ["router"]
