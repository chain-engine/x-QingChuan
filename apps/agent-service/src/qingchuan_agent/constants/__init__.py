"""常量与枚举包（晴川 x-QingChuan，对齐北辰 constants 包形态）。

子模块：
    base      枚举基类族（BaseEnum / StrBaseEnum / IntBaseEnum / FloatBaseEnum）
    constants 全局常量（应用信息 / API 路由）
    enums     业务枚举（通用领域 / Agent 编排域）

说明：Agent 编排域枚举为服务内概念，暂不抽离到共享 domain 包；
若未来双服务需共享 Environment / HttpStatusCode 等，再迁移 qingchuan_domain.constants。
"""

from qingchuan_agent.constants.base import BaseEnum, FloatBaseEnum, IntBaseEnum, StrBaseEnum
from qingchuan_agent.constants.constants import (
    API_PREFIX,
    APP_DESCRIPTION,
    APP_ID,
    APP_NAME,
    APP_VERSION,
)
from qingchuan_agent.constants.enums import (
    AgentRunStatus,
    AgentType,
    ApiResponseMessage,
    Environment,
    HttpHeaders,
    HttpStatusCode,
    RouteMode,
    TaskStatus,
    ToolPermissionLevel,
)

__all__ = [
    "API_PREFIX",
    "APP_DESCRIPTION",
    "APP_ID",
    "APP_NAME",
    "APP_VERSION",
    "AgentRunStatus",
    "AgentType",
    "ApiResponseMessage",
    "BaseEnum",
    "Environment",
    "FloatBaseEnum",
    "HttpHeaders",
    "HttpStatusCode",
    "IntBaseEnum",
    "RouteMode",
    "StrBaseEnum",
    "TaskStatus",
    "ToolPermissionLevel",
]
