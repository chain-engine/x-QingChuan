#!/usr/bin/env python3
"""
Router Module

路由注册
"""

from fastapi import APIRouter

from qingchuan_rag.http_server.v1 import audit_log, document, health, rag, sync

api_router = APIRouter()

# 注册健康检查路由
api_router.include_router(health.router, tags=["系统"])

# 注册RAG路由
api_router.include_router(rag.router, tags=["RAG"])

# 注册文档管理路由
api_router.include_router(document.router, tags=["文档"])

# 注册审计日志路由（内部管理只读）
api_router.include_router(audit_log.router, tags=["审计"])

# 注册人社数据同步路由（触发接口 + 周期调度状态）
api_router.include_router(sync.router, tags=["人社同步"])
