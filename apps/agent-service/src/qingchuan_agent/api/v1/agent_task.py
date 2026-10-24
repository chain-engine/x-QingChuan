#!/usr/bin/env python3
"""Agent 编排管理接口（晴川 x-QingChuan，对齐北辰 api/v1/agent_task）。

    GET    /agents/specs       Agent 注册表列表
    POST   /tasks              提交 Agent 任务（异步化：入队即返回，结果经轮询/SSE获取）
    GET    /tasks              任务列表（可按状态/类型过滤）
    GET    /tasks/{task_id}    任务详情
    GET    /tasks/{task_id}/stream   任务状态流（SSE，实时推送 running→终态）
    POST   /tasks/{task_id}/resume  人工接管恢复（interrupt/resume）
    GET    /events             协作事件列表
    GET    /events/{event_id}  协作事件详情

数据流向：api 层（本文件）→ services（AgentTaskService）→ repositories。
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse

from qingchuan_agent.agents.registry import agent_registry
from qingchuan_agent.api.dependencies import get_task_service
from qingchuan_agent.api.response import success_response
from qingchuan_agent.constants import TaskStatus
from qingchuan_agent.infras.event_bus import EventMessage, get_event_bus
from qingchuan_agent.schemas.agent import AgentTaskCreate, AgentTaskResumeIn
from qingchuan_agent.services.agent_task_service import AgentTaskService
from qingchuan_agent.services.task_worker import TASK_STATE_EVENT

router = APIRouter(tags=["Agent 任务管理"])

# 终态集合（SSE 流到这些状态即关闭连接）
_TERMINAL_STATUSES = {
    TaskStatus.SUCCESS.mark,
    TaskStatus.FAILED.mark,
    TaskStatus.WAITING_HUMAN.mark,
}


@router.get("/agents/specs", summary="Agent 注册表列表")
async def list_agent_specs(request: Request) -> JSONResponse:
    """Agent 注册表列表（无需数据库）。"""
    specs = agent_registry.list_specs()
    return success_response(
        data={
            "items": [
                {
                    "type": str(spec.agent_type),
                    "name": spec.name,
                    "description": spec.description,
                }
                for spec in specs
            ],
            "total": len(specs),
        },
        request=request,
    )


@router.post("/tasks", summary="提交 Agent 任务")
async def submit_task(
    body: AgentTaskCreate,
    request: Request,
    service: AgentTaskService = Depends(get_task_service),
) -> JSONResponse:
    """提交一个 Agent 任务（同步执行）。

    传 task_type 直接路由；留空由 LLM 按 query/payload 动态路由。
    """
    payload = dict(body.payload)
    # 自然语言 query 并入入参，供顶层 RouteResolver 在 task_type 留空时使用
    if body.query and "query" not in payload and "message" not in payload:
        payload["query"] = body.query
    task = await service.submit_task(
        task_type=body.task_type,
        payload=payload,
        timeout_at=body.timeout_at,
    )
    return success_response(data=_task_to_dict(task), request=request)


@router.get("/tasks", summary="Agent 任务列表")
async def list_tasks(
    request: Request,
    status: str | None = Query(default=None, description="按任务状态过滤（TaskStatus）"),
    task_type: str | None = Query(default=None, description="按任务类型过滤（AgentType）"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    service: AgentTaskService = Depends(get_task_service),
) -> JSONResponse:
    """Agent 任务列表（管理后台任务面板）。"""
    items, total = service.list_tasks(
        status=status, task_type=task_type, page=page, page_size=page_size
    )
    return success_response(
        data={
            "items": [_task_to_dict(t) for t in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
        request=request,
    )


@router.get("/tasks/{task_id}", summary="Agent 任务详情")
async def get_task(
    task_id: int,
    request: Request,
    service: AgentTaskService = Depends(get_task_service),
) -> JSONResponse:
    """Agent 任务详情。"""
    task = service.get_task(task_id)
    return success_response(data=_task_to_dict(task), request=request)


@router.get("/tasks/{task_id}/stream", summary="Agent 任务状态流（SSE）")
async def stream_task(
    task_id: int,
    request: Request,
    service: AgentTaskService = Depends(get_task_service),
) -> StreamingResponse:
    """Server-Sent Events：实时推送任务状态（task.state），终态（success/failed/
    waiting_human）后自动关闭。

    - 已终态任务：立即推终态快照并结束（不挂连接）
    - 运行中任务：订阅 EventBus，过滤本任务的 task.state 事件逐条推送
    - 客户端断开 / 终态到达均正常收尾（注销订阅，不泄漏回调）
    """
    task = service.get_task(task_id)  # 不存在则 404

    async def _event_stream():
        bus = get_event_bus()
        queue: asyncio.Queue[EventMessage] = asyncio.Queue()

        def _snapshot(status: str) -> dict:
            return {"task_id": task_id, "status": status, "snapshot": True}

        async def _callback(message: EventMessage) -> None:
            if message.event_type == TASK_STATE_EVENT and message.payload.get("task_id") == task_id:
                queue.put_nowait(message)

        # 先推当前状态快照（轮询兜底：事件可能发生在连接建立前）
        yield f"data: {json.dumps(_snapshot(task.status), ensure_ascii=False)}\n\n"
        if task.status in _TERMINAL_STATUSES:
            return

        await bus.subscribe(_callback)
        try:
            while True:
                message = await queue.get()
                payload = dict(message.payload)
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                if payload.get("status") in _TERMINAL_STATUSES:
                    break
        except asyncio.CancelledError:
            # 客户端断开：正常退出，不视为错误
            pass
        finally:
            await bus.unsubscribe(_callback)

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲，逐事件透传
        },
    )


@router.post("/tasks/{task_id}/resume", summary="恢复人工接管 Agent 任务")
async def resume_task(
    task_id: int,
    body: AgentTaskResumeIn,
    request: Request,
    service: AgentTaskService = Depends(get_task_service),
) -> JSONResponse:
    """人工接管：恢复被 interrupt 暂停的 Agent 任务。"""
    task = await service.resume_task(
        task_id=task_id,
        decision=body.decision,
        remark=body.remark,
        extra=body.extra,
    )
    return success_response(data=_task_to_dict(task), request=request)


@router.get("/events", summary="协作事件列表")
async def list_events(
    request: Request,
    event_type: str | None = Query(default=None, description="按事件类型过滤"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    service: AgentTaskService = Depends(get_task_service),
) -> JSONResponse:
    """协作事件列表（管理后台事件面板 / 审计）。"""
    items, total = service.list_events(event_type=event_type, page=page, page_size=page_size)
    return success_response(
        data={
            "items": [_event_to_dict(ev) for ev in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
        request=request,
    )


@router.get("/events/{event_id}", summary="协作事件详情")
async def get_event(
    event_id: int,
    request: Request,
    service: AgentTaskService = Depends(get_task_service),
) -> JSONResponse:
    """单条协作事件详情（含完整 payload，审计面板查看）。"""
    event = service.get_event(event_id)
    return success_response(data=_event_to_dict(event), request=request)


def _event_to_dict(ev) -> dict:
    """协作事件实体 → 响应字典（列表 / 详情复用）。"""
    return {
        "id": ev.id,
        "event_type": ev.event_type,
        "source_agent": ev.source_agent,
        "target_agent": ev.target_agent,
        "payload": ev.payload,
        "status": ev.status,
        "created_at": ev.created_at.isoformat() if ev.created_at else None,
    }


def _task_to_dict(task) -> dict:
    """任务实体 → 响应字典（骨架统一转换点，后续可用 Pydantic schema 替换）。"""
    return {
        "id": task.id,
        "task_type": task.task_type,
        "payload": task.payload,
        "status": task.status,
        "assignee_agent": task.assignee_agent,
        "thread_id": task.thread_id,
        "retry_count": task.retry_count,
        "max_retries": task.max_retries,
        "error_message": task.error_message,
        "result": task.result,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
    }


__all__ = ["router"]
