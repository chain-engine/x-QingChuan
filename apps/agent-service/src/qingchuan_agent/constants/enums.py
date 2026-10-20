#!/usr/bin/env python3
"""
Enums Module

项目全部枚举定义，统一按 (mark, desc) 二元组声明。

继承判断规则（依据 mark 的原生类型）：
    mark 为 int 的枚举（如 HTTP 状态码） → IntBaseEnum
    mark 为 str 的枚举（状态、类型、名称等） → StrBaseEnum
"""

from qingchuan_agent.constants.base import IntBaseEnum, StrBaseEnum

# ====================================
# 通用领域
# ====================================


class Environment(StrBaseEnum):
    """运行环境"""

    DEVELOPMENT = "development", "开发"
    TESTING = "testing", "测试"
    PRODUCTION = "production", "生产"


class HttpStatusCode(IntBaseEnum):
    """HTTP 状态码"""

    OK = 200, "成功"
    BAD_REQUEST = 400, "请求错误"
    UNAUTHORIZED = 401, "未授权"
    FORBIDDEN = 403, "禁止访问"
    NOT_FOUND = 404, "资源不存在"
    CONFLICT = 409, "资源冲突"
    UNPROCESSABLE_ENTITY = 422, "参数校验失败"
    INTERNAL_SERVER_ERROR = 500, "服务器内部错误"
    BAD_GATEWAY = 502, "网关错误"


class ApiResponseMessage(StrBaseEnum):
    """统一响应消息文案"""

    VALIDATION_ERROR = "参数校验失败", "参数校验失败"


class HttpHeaders(StrBaseEnum):
    """HTTP 请求 / 响应头"""

    X_REQUEST_ID = "X-Request-ID", "请求ID"


# ====================================
# Agent 编排域
# ====================================


class AgentType(StrBaseEnum):
    """Agent 类型（注册表路由键）"""

    AGENT_A = "agent_a", "RAG 问答 Agent"


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


class ToolPermissionLevel(StrBaseEnum):
    """工具权限级别（read 可直调 / write 由人工执行）"""

    READ = "read", "只读"
    WRITE = "write", "写"


__all__ = [
    "AgentRunStatus",
    "AgentType",
    "ApiResponseMessage",
    "Environment",
    "HttpHeaders",
    "HttpStatusCode",
    "RouteMode",
    "TaskStatus",
    "ToolPermissionLevel",
]
