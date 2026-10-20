#!/usr/bin/env python3
"""中央路由注册模块（晴川 x-QingChuan，对齐北辰 api/router）。

汇聚 v1 业务路由，统一挂载 /api/v1 前缀：
    /api/v1/health       健康/版本探针
    /api/v1/agents       Agent 注册表
    /api/v1/tasks        Agent 任务（提交 / 查询 / 人工接管）
    /api/v1/events       协作事件（审计）
未来扩展 v2 时新增 api/v2/ 聚合后于此 include 即可。
"""

from fastapi import APIRouter

from qingchuan_agent.api.v1 import v1_router
from qingchuan_agent.constants import API_PREFIX

# 全局业务路由（对外完整路径 /api/v1/...）
global_router = APIRouter(prefix=API_PREFIX)
global_router.include_router(v1_router)

__all__ = ["global_router"]
