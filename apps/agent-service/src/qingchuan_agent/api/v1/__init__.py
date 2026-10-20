"""API v1 路由包（晴川 x-QingChuan，对齐北辰 api/v1 聚合方式）。

在此聚合所有 v1 版本下的业务子路由（v1 前缀已并入全局 router 的 /api/v1）。

当前 v1 模块：
    health      健康/版本探针
    agent_task  Agent 编排（任务提交/查询/人工接管/事件）
"""

from fastapi import APIRouter

from qingchuan_agent.api.v1 import agent_task, health

# v1 聚合路由（无额外前缀，全局 router 已挂 /api/v1）
v1_router = APIRouter()

# 健康与版本探针
v1_router.include_router(health.router)

# Agent 编排
v1_router.include_router(agent_task.router)

__all__ = ["v1_router"]
