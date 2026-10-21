"""
核心基础设施包（晴川 x-QingChuan，对齐北辰 core 包形态）
提供应用程序运行所需的核心组件：
    - config: 配置管理（分段 + 单例 + 校验）
    - logger: 日志管理（loguru，JSON 文件 + request_id）
    - exceptions: 异常处理（异常类 re-export qingchuan_domain + FastAPI 处理器）
    - middleware: HTTP 中间件
    - response: 统一 HTTP 响应构造
"""

from qingchuan_agent.core.config import Settings, settings
from qingchuan_agent.core.exceptions import (
    AgentException,
    AppException,
    BusinessError,
    ConflictError,
    DatabaseError,
    ExternalServiceError,
    ForbiddenError,
    NotFoundError,
    SystemError,
    UnauthorizedError,
    ValidationError,
    register_exception_handlers,
)
from qingchuan_agent.core.logger import logger, setup_logging
from qingchuan_agent.core.middleware import AuthMiddleware, RequestIDMiddleware

__all__ = [
    "AgentException",
    "AppException",
    "AuthMiddleware",
    "BusinessError",
    "ConflictError",
    "DatabaseError",
    "ExternalServiceError",
    "ForbiddenError",
    "NotFoundError",
    "RequestIDMiddleware",
    "Settings",
    "SystemError",
    "UnauthorizedError",
    "ValidationError",
    "logger",
    "register_exception_handlers",
    "settings",
    "setup_logging",
]
