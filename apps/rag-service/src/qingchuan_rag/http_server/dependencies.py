#!/usr/bin/env python3
"""HTTP 接入层统一依赖管理模块。

承载 HTTP 接入层（http_server/）的全部依赖注入：
- 业务服务依赖：get_rag_service / get_document_service / get_sync_service
  （从 app.state 取，避免重复初始化）
- 操作人上下文（get_app_operator_context，供审计 / 日志使用）

晴川为内部服务，不设开放平台机器身份鉴权：所有操作人统一记为
internal（operator_id="internal"），审计日志仍完整记录实体与动作。

各 v1 路由模块一律从本模块导入依赖，不在路由文件内再定义。
"""

from __future__ import annotations

from typing import Any

from fastapi import Request

from qingchuan_rag.services.audit_service import AuditService
from qingchuan_rag.services.document_service import DocumentService
from qingchuan_rag.services.rag_service import RAGService
from qingchuan_rag.services.sync_service import SyncService


def get_rag_service(request: Request) -> RAGService:
    """依赖注入：获取 RAG 服务（应用启动时初始化的共享实例）"""
    return request.app.state.rag_service


def get_document_service(request: Request) -> DocumentService:
    """依赖注入：获取文档服务（应用启动时初始化的共享实例）"""
    return request.app.state.document_service


def get_audit_service(request: Request) -> AuditService:
    """依赖注入：获取审计日志服务（无状态共享实例）。"""
    return request.app.state.audit_service


def get_sync_service(request: Request) -> SyncService:
    """依赖注入：获取人社数据同步服务（应用启动时初始化的共享实例）。"""
    return request.app.state.sync_service


def get_app_operator_context(request: Request | None = None) -> dict[str, Any]:
    """构造操作人上下文（供写操作审计 / 日志使用）。

    晴川为内部服务，不设应用鉴权，操作人统一记为 internal；
    ip_address 取自请求来源（优先反向代理透传的真实 IP）。
    """
    client_ip = None
    if request is not None:
        forwarded = request.headers.get("X-Forwarded-For")
        client_ip = (forwarded.split(",")[0].strip() if forwarded else None) or (
            request.client.host if request.client else None
        )
    return {
        "operator_id": "internal",
        "operator_name": "internal",
        "ip_address": client_ip,
    }


__all__ = [
    "get_rag_service",
    "get_document_service",
    "get_sync_service",
    "get_audit_service",
    "get_app_operator_context",
]
