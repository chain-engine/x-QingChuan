#!/usr/bin/env python3
"""健康检查与版本探针（晴川 x-QingChuan，对齐北辰 api/v1/health）。

/health：服务存活 + 依赖状态（db / agent runtime）
/version：应用版本信息
探针不依赖数据库，供负载均衡 / 运维监控使用。
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from qingchuan_agent.api.response import success_response
from qingchuan_agent.constants import APP_NAME, APP_VERSION
from qingchuan_agent.core.config import settings

router = APIRouter(tags=["健康检查"])


@router.get("/health", summary="服务健康检查")
async def health(request: Request) -> JSONResponse:
    """服务健康检查：返回各依赖组件的可用状态。"""
    db_status = "disabled"
    if settings.database.enabled:
        from qingchuan_agent.infras.database import get_cached_database_provider

        db_status = "ok" if get_cached_database_provider().check_connection() else "error"

    from qingchuan_agent.agents.runtime import get_agent_runtime

    runtime = get_agent_runtime()

    return success_response(
        data={
            "status": "ok",
            "app": APP_NAME,
            "version": APP_VERSION,
            "env": settings.app_env,
            "dependencies": {
                "database": db_status,
                "agent_runtime": (
                    "ready" if runtime.build_orchestrator() is not None else "not_ready"
                ),
            },
            "time": datetime.now(UTC).isoformat(),
        },
        request=request,
    )


@router.get("/version", summary="应用版本信息")
async def version(request: Request) -> JSONResponse:
    """应用版本信息。"""
    return success_response(
        data={
            "app_id": "x-QingChuan",
            "app_name": APP_NAME,
            "version": APP_VERSION,
            "python_requires": ">=3.12",
        },
        request=request,
    )


__all__ = ["router"]
