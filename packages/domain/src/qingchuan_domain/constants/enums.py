"""共享领域包：跨服务通用枚举（单一事实来源）。

双服务（agent-service / rag-service）共用的枚举统一在此定义，
服务内专属枚举（Agent 编排状态、RAG 文档状态等）保留在各服务 constants。

继承判断规则（依据 mark 的原生类型）：
    mark 为 int 的枚举（如 HTTP 状态码） → IntBaseEnum
    mark 为 str 的枚举（状态、类型、名称等） → StrBaseEnum
"""

from qingchuan_domain.constants.base import IntBaseEnum, StrBaseEnum


class HttpStatus(IntBaseEnum):
    """HTTP 状态码（agent 原 HttpStatusCode 与 rag 原 HttpStatus 合并）"""

    OK = 200, "成功"
    CREATED = 201, "已创建"
    BAD_REQUEST = 400, "请求错误"
    UNAUTHORIZED = 401, "未授权"
    FORBIDDEN = 403, "禁止访问"
    NOT_FOUND = 404, "资源不存在"
    CONFLICT = 409, "资源冲突"
    UNPROCESSABLE_ENTITY = 422, "参数校验失败"
    TOO_MANY_REQUESTS = 429, "请求过于频繁"
    INTERNAL_SERVER_ERROR = 500, "服务器内部错误"
    BAD_GATEWAY = 502, "网关错误"


class Environment(StrBaseEnum):
    """运行环境"""

    DEVELOPMENT = "development", "开发"
    TESTING = "testing", "测试"
    PRODUCTION = "production", "生产"


class AgentType(StrBaseEnum):
    """Agent 类型（注册表路由键）"""

    AGENT_A = "agent_a", "RAG 问答 Agent"


class ToolPermissionLevel(StrBaseEnum):
    """工具权限级别（read 可直调 / write 由人工执行）"""

    READ = "read", "只读"
    WRITE = "write", "写"


__all__ = [
    "AgentType",
    "Environment",
    "HttpStatus",
    "ToolPermissionLevel",
]
