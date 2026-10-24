#!/usr/bin/env python3
"""应用配置管理（晴川 x-QingChuan，对齐 rag-service core/config.py 手搓风格）。

全局配置中心：支持从环境变量和 YAML 配置文件读取配置。
优先级：环境变量 > YAML 配置文件 > 默认配置。

分段配置各自带独立环境变量前缀（QINGCHUAN_AGENT_*），避免扁平面板式配置散落；
配置非法直接阻断启动（validate，生产环境强制校验清单见 Settings.validate）。

Usage:
    from qingchuan_agent.core.config import settings
    level = settings.logging.level
    db_url = settings.database.url
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final
from urllib.parse import quote_plus

import yaml
from dotenv import load_dotenv

from qingchuan_agent.constants import Environment, RouteMode

# 仓库根 .env（本地开发单一配置源；任意 CWD 启动均能加载，避免 .env 相对 CWD 失效）
QINGCHUAN_ROOT_ENV: Final[Path] = Path(__file__).resolve().parents[5] / ".env"


@dataclass
class AppConfig:
    """应用信息配置（app_env / service_name，独立成段便于 env 映射与属性快捷方式）。"""

    env: str = Environment.DEVELOPMENT.mark
    service_name: str = "agent-service"


@dataclass
class ServerConfig:
    """HTTP 服务配置（uvicorn 监听）。"""

    host: str = "0.0.0.0"
    port: int = 8020
    debug: bool = True
    workers: int = 1


@dataclass
class LoggingConfig:
    """日志配置。"""

    level: str = "INFO"
    format: str = "console"  # "json" | "console"
    # 相对路径由 logger 按服务根目录（src 的上级目录）解析，
    # 任意 CWD 启动均落位 apps/agent-service/logs/，文件名 x-QingChuan-{time:YYYYMMDDHHmmss}.log
    file_path: str = "./logs/x-QingChuan-{time:YYYYMMDDHHmmss}.log"
    rotation: str = "1 day"
    retention: str = "7 days"
    compression: str = "zip"
    console_output: bool = True


@dataclass
class CORSConfig:
    """跨域配置。"""

    enabled: bool = True
    origins: list[str] = field(default_factory=lambda: ["*"])
    allow_credentials: bool = True
    allow_methods: list[str] = field(default_factory=lambda: ["*"])
    allow_headers: list[str] = field(default_factory=lambda: ["*"])


@dataclass
class DatabaseConfig:
    """数据库配置（Agent 任务 / 事件持久化；骨架阶段默认关闭，可无库启动）。"""

    enabled: bool = False  # 骨架阶段默认关闭，业务接入时开启
    host: str = "localhost"
    port: int = 3306
    user: str = "root"
    password: str = ""
    database: str = "qingchuan"
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30
    pool_recycle: int = 3600
    echo: bool = False

    @property
    def url(self) -> str:
        """生成 SQLAlchemy 连接串（mysql+pymysql）。

        无密码（本地开发 root 空密码）也生成合法连接串，而不是返回空串——
        空串会让 MySqlProvider 直接拒绝连接，堵死本地无密码 MySQL 场景。
        """
        pwd = quote_plus(self.password) if self.password else ""
        auth = f"{quote_plus(self.user)}:{pwd}@" if self.user else ""
        return f"mysql+pymysql://{auth}{self.host}:{self.port}/{quote_plus(self.database)}"


@dataclass
class AiLLMSettings:
    """大模型配置（LangChain ChatOpenAI 兼容接口；骨架阶段不配 key 走 Mock）。

    类名保留原 pydantic-settings 时代的 AiLLMSettings（infras/llm.py 按此名导入），
    字段与环境变量前缀（QINGCHUAN_AGENT_AI_LLM_*）均保持不变。
    """

    base_url: str = ""
    api_key: str = ""  # 敏感信息，仅通过环境变量 / .env 注入
    model: str = "deepseek-chat"
    temperature: float = 0.7
    max_tokens: int = 2048
    timeout_seconds: int = 60


@dataclass
class AiConfig:
    """AI 整体配置（本期骨架：LLM 预留，节点内业务为 mock）。"""

    enabled: bool = True
    llm: AiLLMSettings = field(default_factory=AiLLMSettings)


@dataclass
class AgentConfig:
    """Agent 编排配置（调度中枢 / 子图 / 任务状态机）。"""

    route_mode: str = RouteMode.EXPLICIT.mark  # explicit / llm / hybrid
    checkpoint: str = "memory"  # memory / redis（redis 需 QINGCHUAN_AGENT_REDIS_ENABLED=true）
    confidence_threshold: float = 0.7  # LLM 动态路由采信阈值
    task_max_retries: int = 3  # 失败重试上限
    task_timeout_seconds: int = 300  # 单任务超时


@dataclass
class RedisConfig:
    """Redis 配置（checkpoint 与事件总线共用同一实例 / 连接配置）。

    - checkpoint：agent.checkpoint=redis 时，LangGraph RedisSaver 走同步连接
    - 事件总线：redis.enabled=true 时，EventBus 工厂切换 Redis Pub/Sub（跨进程广播）
    两者共用同一 Redis 实例（同 host/port/db），分别持有同步 / 异步连接池。
    """

    enabled: bool = False  # 默认关闭：骨架期可无 Redis 启动（memory checkpoint + 内存事件总线）
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    username: str = ""
    password: str = ""  # 敏感信息，仅通过环境变量 / .env 注入
    ssl: bool = False  # true 时使用 rediss://（TLS）
    url: str = ""  # 可选完整连接 URL（redis://...），提供时优先于 host/port 组装
    socket_timeout: float = 5.0

    @property
    def connection_url(self) -> str:
        """生成 Redis 连接串（url 优先，否则 host/port/db 组装）。"""
        if self.url:
            return self.url
        auth = (
            f"{quote_plus(self.username)}:{quote_plus(self.password)}@"
            if self.username or self.password
            else ""
        )
        scheme = "rediss" if self.ssl else "redis"
        return f"{scheme}://{auth}{self.host}:{self.port}/{self.db}"


@dataclass
class RagClientConfig:
    """rag-service 客户端配置（MCP 优先，HTTP 兜底）。"""

    # MCP 主链路：rag-service 以 streamable HTTP 挂载 /mcp（见 rag-service main.py），
    # agent 经 qingchuan_common.mcp.MCPClient 连接调用 retrieve_docs / rag_query
    mcp_url: str = "http://rag-service:8010/mcp"
    # HTTP 兜底链路（预留：MCP 不可用时降级调 /api/v1/rag/*，当前未实现）
    http_base_url: str = "http://rag-service:8010"
    mcp_timeout_seconds: float = 60.0


class Settings:
    """应用配置类（对齐 rag-service Settings 手搓形态）。

    支持从环境变量和 YAML 配置文件读取配置。
    优先级：环境变量 > YAML 配置文件 > 默认配置。
    配置非法直接阻断启动（validate；生产环境强制校验清单见 validate 内注释）。
    """

    CONFIG_FILE_PATH: Final[str] = "config.yaml"

    def __init__(self) -> None:
        """初始化配置"""
        load_dotenv(QINGCHUAN_ROOT_ENV)
        self._config: dict[str, Any] = self._load_config()
        self._parse_config()
        self.validate()

    def _get_default_config(self) -> dict[str, Any]:
        """获取默认配置"""
        return {
            "app": {
                "env": Environment.DEVELOPMENT.mark,
                "service_name": "agent-service",
            },
            "server": {
                "host": "0.0.0.0",
                "port": 8020,
                "debug": True,
                "workers": 1,
            },
            "logging": {
                "level": "INFO",
                "format": "console",
                "file_path": "./logs/x-QingChuan-{time:YYYYMMDDHHmmss}.log",
                "rotation": "1 day",
                "retention": "7 days",
                "compression": "zip",
                "console_output": True,
            },
            "cors": {
                "enabled": True,
                "origins": ["*"],
                "allow_credentials": True,
                "allow_methods": ["*"],
                "allow_headers": ["*"],
            },
            "database": {
                "enabled": False,
                "host": "localhost",
                "port": 3306,
                "user": "root",
                "password": "",
                "database": "qingchuan",
                "pool_size": 5,
                "max_overflow": 10,
                "pool_timeout": 30,
                "pool_recycle": 3600,
                "echo": False,
            },
            "ai": {
                "enabled": True,
                "llm": {
                    "base_url": "",
                    "api_key": "",
                    "model": "deepseek-chat",
                    "temperature": 0.7,
                    "max_tokens": 2048,
                    "timeout_seconds": 60,
                },
            },
            "agent": {
                "route_mode": RouteMode.EXPLICIT.mark,
                "checkpoint": "memory",
                "confidence_threshold": 0.7,
                "task_max_retries": 3,
                "task_timeout_seconds": 300,
            },
            "redis": {
                "enabled": False,
                "host": "localhost",
                "port": 6379,
                "db": 0,
                "username": "",
                "password": "",
                "ssl": False,
                "url": "",
                "socket_timeout": 5.0,
            },
            "rag": {
                "mcp_url": "http://rag-service:8010/mcp",
                "http_base_url": "http://rag-service:8010",
                "mcp_timeout_seconds": 60.0,
            },
        }

    def _load_config(self) -> dict[str, Any]:
        """加载配置

        优先级：环境变量 > YAML 配置文件 > 默认配置
        """
        config: dict[str, Any] = self._get_default_config()
        self._load_from_file(config)
        self._load_from_env(config)
        return config

    def _load_from_file(self, config: dict[str, Any]) -> None:
        """从 YAML 文件加载配置（存在才加载；仓库默认无此文件即纯 env 驱动）"""
        config_file: Path = Path(self.CONFIG_FILE_PATH)
        if config_file.exists():
            try:
                with open(config_file, encoding="utf-8") as f:
                    file_config: dict[str, Any] = yaml.safe_load(f) or {}
                self._merge_config(config, file_config)
            except Exception as e:
                print(f"Warning: Cannot load config file {self.CONFIG_FILE_PATH}: {e}")

    def _merge_config(self, base: dict[str, Any], override: dict[str, Any]) -> None:
        """递归合并配置"""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value

    def _parse_list(self, value: str) -> list[str]:
        """环境变量 → list[str]：兼容 JSON 数组（["a","b"]）与逗号分隔（a,b）两种写法。"""
        text = value.strip()
        if text.startswith("[") and text.endswith("]"):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return [str(x) for x in parsed]
            except ValueError:
                pass
        return [x.strip() for x in text.split(",") if x.strip()]

    def _to_bool(self, value: str) -> bool:
        return str(value).lower() in ("true", "1", "yes")

    def _load_from_env(self, config: dict[str, Any]) -> None:
        """从环境变量加载配置（env 变量名与 .env 完全保持 QINGCHUAN_AGENT_* 前缀不变）"""
        env_mappings = {
            # 应用信息
            "QINGCHUAN_AGENT_APP_ENV": ("app", "env", str),
            "QINGCHUAN_AGENT_SERVICE_NAME": ("app", "service_name", str),
            # 服务
            "QINGCHUAN_AGENT_SERVER_HOST": ("server", "host", str),
            "QINGCHUAN_AGENT_SERVER_PORT": ("server", "port", int),
            "QINGCHUAN_AGENT_SERVER_DEBUG": ("server", "debug", self._to_bool),
            "QINGCHUAN_AGENT_SERVER_WORKERS": ("server", "workers", int),
            # 日志
            "QINGCHUAN_AGENT_LOGGING_LEVEL": ("logging", "level", str),
            "QINGCHUAN_AGENT_LOGGING_FORMAT": ("logging", "format", str),
            "QINGCHUAN_AGENT_LOGGING_FILE_PATH": ("logging", "file_path", str),
            "QINGCHUAN_AGENT_LOGGING_ROTATION": ("logging", "rotation", str),
            "QINGCHUAN_AGENT_LOGGING_RETENTION": ("logging", "retention", str),
            "QINGCHUAN_AGENT_LOGGING_COMPRESSION": ("logging", "compression", str),
            "QINGCHUAN_AGENT_LOGGING_CONSOLE_OUTPUT": (
                "logging",
                "console_output",
                self._to_bool,
            ),
            # CORS
            "QINGCHUAN_AGENT_CORS_ENABLED": ("cors", "enabled", self._to_bool),
            "QINGCHUAN_AGENT_CORS_ORIGINS": ("cors", "origins", self._parse_list),
            "QINGCHUAN_AGENT_CORS_ALLOW_CREDENTIALS": (
                "cors",
                "allow_credentials",
                self._to_bool,
            ),
            "QINGCHUAN_AGENT_CORS_ALLOW_METHODS": ("cors", "allow_methods", self._parse_list),
            "QINGCHUAN_AGENT_CORS_ALLOW_HEADERS": ("cors", "allow_headers", self._parse_list),
            # 数据库
            "QINGCHUAN_AGENT_DATABASE_ENABLED": ("database", "enabled", self._to_bool),
            "QINGCHUAN_AGENT_DATABASE_HOST": ("database", "host", str),
            "QINGCHUAN_AGENT_DATABASE_PORT": ("database", "port", int),
            "QINGCHUAN_AGENT_DATABASE_USER": ("database", "user", str),
            "QINGCHUAN_AGENT_DATABASE_PASSWORD": ("database", "password", str),
            "QINGCHUAN_AGENT_DATABASE_DATABASE": ("database", "database", str),
            "QINGCHUAN_AGENT_DATABASE_POOL_SIZE": ("database", "pool_size", int),
            "QINGCHUAN_AGENT_DATABASE_MAX_OVERFLOW": ("database", "max_overflow", int),
            "QINGCHUAN_AGENT_DATABASE_POOL_TIMEOUT": ("database", "pool_timeout", int),
            "QINGCHUAN_AGENT_DATABASE_POOL_RECYCLE": ("database", "pool_recycle", int),
            "QINGCHUAN_AGENT_DATABASE_ECHO": ("database", "echo", self._to_bool),
            # AI / LLM
            "QINGCHUAN_AGENT_AI_ENABLED": ("ai", "enabled", self._to_bool),
            "QINGCHUAN_AGENT_AI_LLM_BASE_URL": ("ai.llm", "base_url", str),
            "QINGCHUAN_AGENT_AI_LLM_API_KEY": ("ai.llm", "api_key", str),
            "QINGCHUAN_AGENT_AI_LLM_MODEL": ("ai.llm", "model", str),
            "QINGCHUAN_AGENT_AI_LLM_TEMPERATURE": ("ai.llm", "temperature", float),
            "QINGCHUAN_AGENT_AI_LLM_MAX_TOKENS": ("ai.llm", "max_tokens", int),
            "QINGCHUAN_AGENT_AI_LLM_TIMEOUT_SECONDS": ("ai.llm", "timeout_seconds", int),
            # Agent 编排
            "QINGCHUAN_AGENT_AGENT_ROUTE_MODE": ("agent", "route_mode", str),
            "QINGCHUAN_AGENT_AGENT_CHECKPOINT": ("agent", "checkpoint", str),
            "QINGCHUAN_AGENT_AGENT_CONFIDENCE_THRESHOLD": (
                "agent",
                "confidence_threshold",
                float,
            ),
            "QINGCHUAN_AGENT_AGENT_TASK_MAX_RETRIES": ("agent", "task_max_retries", int),
            "QINGCHUAN_AGENT_AGENT_TASK_TIMEOUT_SECONDS": (
                "agent",
                "task_timeout_seconds",
                int,
            ),
            # Redis
            "QINGCHUAN_AGENT_REDIS_ENABLED": ("redis", "enabled", self._to_bool),
            "QINGCHUAN_AGENT_REDIS_HOST": ("redis", "host", str),
            "QINGCHUAN_AGENT_REDIS_PORT": ("redis", "port", int),
            "QINGCHUAN_AGENT_REDIS_DB": ("redis", "db", int),
            "QINGCHUAN_AGENT_REDIS_USERNAME": ("redis", "username", str),
            "QINGCHUAN_AGENT_REDIS_PASSWORD": ("redis", "password", str),
            "QINGCHUAN_AGENT_REDIS_SSL": ("redis", "ssl", self._to_bool),
            "QINGCHUAN_AGENT_REDIS_URL": ("redis", "url", str),
            "QINGCHUAN_AGENT_REDIS_SOCKET_TIMEOUT": ("redis", "socket_timeout", float),
            # rag-service 客户端
            "QINGCHUAN_AGENT_RAG_MCP_URL": ("rag", "mcp_url", str),
            "QINGCHUAN_AGENT_RAG_HTTP_BASE_URL": ("rag", "http_base_url", str),
            "QINGCHUAN_AGENT_RAG_MCP_TIMEOUT_SECONDS": ("rag", "mcp_timeout_seconds", float),
        }

        for env_key, (section, field_key, converter) in env_mappings.items():
            env_value = os.environ.get(env_key)
            if env_value is None:
                continue
            try:
                # 嵌套段（如 ai.llm）按 "." 逐级下钻
                target: dict[str, Any] = config
                for part in section.split("."):
                    target = target[part]
                target[field_key] = converter(env_value)
            except (ValueError, TypeError, KeyError):
                pass

    def _parse_config(self) -> None:
        """解析配置到具体配置对象"""
        self.app = AppConfig(**self._config["app"])
        self.server = ServerConfig(**self._config["server"])
        self.logging = LoggingConfig(**self._config["logging"])
        self.cors = CORSConfig(**self._config["cors"])
        self.database = DatabaseConfig(**self._config["database"])
        self.ai = AiConfig(
            enabled=self._config["ai"]["enabled"],
            llm=AiLLMSettings(**self._config["ai"]["llm"]),
        )
        self.agent = AgentConfig(**self._config["agent"])
        self.redis = RedisConfig(**self._config["redis"])
        self.rag = RagClientConfig(**self._config["rag"])

    def reload(self) -> None:
        """重新加载配置"""
        self._config = self._load_config()
        self._parse_config()
        self.validate()

    # === 应用信息 ===
    @property
    def app_env(self) -> str:
        return self.app.env

    @property
    def service_name(self) -> str:
        return self.app.service_name

    @property
    def is_development(self) -> bool:
        return self.app.env == Environment.DEVELOPMENT.mark

    @property
    def is_production(self) -> bool:
        return self.app.env == Environment.PRODUCTION.mark

    # === 服务器 ===
    @property
    def SERVER_HOST(self) -> str:
        return self.server.host

    @property
    def SERVER_PORT(self) -> int:
        return self.server.port

    @property
    def DEBUG(self) -> bool:
        return self.server.debug

    @property
    def SERVER_WORKERS(self) -> int:
        return self.server.workers

    # === 日志 ===
    @property
    def LOG_LEVEL(self) -> str:
        return self.logging.level

    @property
    def LOG_FORMAT(self) -> str:
        return self.logging.format

    @property
    def LOG_FILE_PATH(self) -> str:
        return self.logging.file_path

    @property
    def LOG_ROTATION(self) -> str:
        return self.logging.rotation

    @property
    def LOG_RETENTION(self) -> str:
        return self.logging.retention

    @property
    def LOG_COMPRESSION(self) -> str:
        return self.logging.compression

    @property
    def LOG_CONSOLE_OUTPUT(self) -> bool:
        return self.logging.console_output

    # === CORS ===
    @property
    def CORS_ENABLED(self) -> bool:
        return self.cors.enabled

    @property
    def CORS_ALLOW_ORIGINS(self) -> str:
        if isinstance(self.cors.origins, list):
            return ",".join(self.cors.origins)
        return self.cors.origins

    @property
    def CORS_ALLOW_CREDENTIALS(self) -> bool:
        return self.cors.allow_credentials

    @property
    def CORS_ALLOW_METHODS(self) -> list[str]:
        return self.cors.allow_methods

    @property
    def CORS_ALLOW_HEADERS(self) -> list[str]:
        return self.cors.allow_headers

    # === 数据库 ===
    @property
    def DATABASE_ENABLED(self) -> bool:
        return self.database.enabled

    @property
    def DATABASE_URL(self) -> str:
        return self.database.url

    # === AI / LLM ===
    @property
    def AI_ENABLED(self) -> bool:
        return self.ai.enabled

    @property
    def AI_LLM_BASE_URL(self) -> str:
        return self.ai.llm.base_url

    @property
    def AI_LLM_API_KEY(self) -> str:
        return self.ai.llm.api_key

    @property
    def AI_LLM_MODEL(self) -> str:
        return self.ai.llm.model

    @property
    def AI_LLM_TEMPERATURE(self) -> float:
        return self.ai.llm.temperature

    @property
    def AI_LLM_MAX_TOKENS(self) -> int:
        return self.ai.llm.max_tokens

    @property
    def AI_LLM_TIMEOUT_SECONDS(self) -> int:
        return self.ai.llm.timeout_seconds

    # === Agent 编排 ===
    @property
    def AGENT_ROUTE_MODE(self) -> str:
        return self.agent.route_mode

    @property
    def AGENT_CHECKPOINT(self) -> str:
        return self.agent.checkpoint

    @property
    def AGENT_CONFIDENCE_THRESHOLD(self) -> float:
        return self.agent.confidence_threshold

    @property
    def AGENT_TASK_MAX_RETRIES(self) -> int:
        return self.agent.task_max_retries

    @property
    def AGENT_TASK_TIMEOUT_SECONDS(self) -> int:
        return self.agent.task_timeout_seconds

    # === Redis ===
    @property
    def REDIS_ENABLED(self) -> bool:
        return self.redis.enabled

    @property
    def REDIS_CONNECTION_URL(self) -> str:
        return self.redis.connection_url

    @property
    def REDIS_SOCKET_TIMEOUT(self) -> float:
        return self.redis.socket_timeout

    # === rag-service 客户端 ===
    @property
    def RAG_MCP_URL(self) -> str:
        return self.rag.mcp_url

    @property
    def RAG_HTTP_BASE_URL(self) -> str:
        return self.rag.http_base_url

    @property
    def RAG_MCP_TIMEOUT_SECONDS(self) -> float:
        return self.rag.mcp_timeout_seconds

    # === 配置校验 ===
    def validate(self) -> None:
        """验证配置合法性，配置错误直接阻断启动。

        与 rag-service 的差异：agent 保留生产环境强制校验清单
        （DEBUG / CORS / checkpoint / Redis 均为硬约束）。
        """
        valid_modes = {mode.mark for mode in RouteMode}
        if self.agent.route_mode not in valid_modes:
            raise ValueError(
                f"QINGCHUAN_AGENT_AGENT_ROUTE_MODE 非法：{self.agent.route_mode}"
                f"（可选 {sorted(valid_modes)}）"
            )
        if self.agent.checkpoint not in ("memory", "redis"):
            raise ValueError(
                f"QINGCHUAN_AGENT_AGENT_CHECKPOINT 非法：{self.agent.checkpoint}"
                f"（可选 memory / redis）"
            )
        if self.ai.llm.api_key and len(self.ai.llm.api_key) < 8:
            raise ValueError(
                "QINGCHUAN_AGENT_AI_LLM_API_KEY 长度异常（至少 8 字符，未配置可留空走 mock）"
            )
        if self.is_production:
            if self.server.debug:
                raise ValueError("生产环境禁止开启 DEBUG（QINGCHUAN_AGENT_SERVER_DEBUG=false）")
            if self.database.enabled and (not self.database.host or not self.database.database):
                raise ValueError(
                    "生产环境启用数据库时必须配置 QINGCHUAN_AGENT_DATABASE_HOST / DATABASE"
                )
            if "*" in self.cors.origins:
                raise ValueError(
                    "生产环境 QINGCHUAN_AGENT_CORS_ORIGINS 不能为 *，请显式配置允许的域名列表"
                )
            if self.agent.checkpoint == "redis" and not self.redis.enabled:
                raise ValueError(
                    "agent.checkpoint=redis 时须启用 Redis（QINGCHUAN_AGENT_REDIS_ENABLED=true）"
                )
            if self.agent.checkpoint == "memory":
                raise ValueError(
                    "生产环境（APP_ENV=production）禁止使用 memory checkpoint，请配置 redis"
                )
            if not self.redis.enabled:
                raise ValueError(
                    "生产环境（APP_ENV=production）要求启用 Redis："
                    "事件总线与人工接管断点续跑均依赖 Redis"
                )


# 创建全局配置实例（导入即加载并校验，配置错误直接阻断启动）
settings: Final[Settings] = Settings()


def get_settings() -> Settings:
    """获取全局配置单例。"""
    return settings


__all__ = [
    "AgentConfig",
    "AiConfig",
    "AiLLMSettings",
    "AppConfig",
    "CORSConfig",
    "DatabaseConfig",
    "LoggingConfig",
    "RagClientConfig",
    "RedisConfig",
    "ServerConfig",
    "Settings",
    "get_settings",
    "settings",
]
