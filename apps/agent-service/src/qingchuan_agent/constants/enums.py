#!/usr/bin/env python3
"""
Enums Module

跨服务共享枚举（Environment / HttpStatus / AgentType / ToolPermissionLevel）
单一事实来源在 qingchuan_domain.constants.enums，本模块 re-export；
Agent 编排域专属枚举（TaskStatus / AgentRunStatus / RouteMode 等）保留在此。
"""

from qingchuan_domain.constants.enums import (
    AgentType,
    Environment,
    HttpHeaders,
    HttpStatus,
    ToolPermissionLevel,
)

from qingchuan_agent.constants.base import StrBaseEnum

# ====================================
# 通用领域（re-export 共享领域包）
# ====================================
# Environment / HttpStatus / HttpHeaders / AgentType / ToolPermissionLevel 见 domain constants

# ====================================
# Agent 编排域（服务内概念）
# ====================================


class ApiResponseMessage(StrBaseEnum):
    """统一响应消息文案"""

    VALIDATION_ERROR = "参数校验失败", "参数校验失败"


class HumanDecision(StrBaseEnum):
    """人工接管决策（waiting_human 任务的用户处理结果）"""

    APPROVE = "approve", "批准"
    REJECT = "reject", "拒绝"
    ADJUST = "adjust", "调整"


class TaskStatus(StrBaseEnum):
    """任务状态（顶层编排与子图共用）"""

    RUNNING = "running", "执行中"
    SUCCESS = "success", "成功"
    FAILED = "failed", "失败"
    WAITING_HUMAN = "waiting_human", "等待人工"


class AgentRunStatus(StrBaseEnum):
    """运行时状态（可观测面板用）"""

    IDLE = "idle", "空闲"
    RUNNING = "running", "执行中"


class RouteMode(StrBaseEnum):
    """路由模式"""

    EXPLICIT = "explicit", "显式路由"
    LLM = "llm", "LLM 动态路由"
    HYBRID = "hybrid", "混合路由"


__all__ = [
    "AgentRunStatus",
    "AgentType",
    "ApiResponseMessage",
    "Environment",
    "HttpHeaders",
    "HttpStatus",
    "HumanDecision",
    "RouteMode",
    "TaskStatus",
    "ToolPermissionLevel",
]
