#!/usr/bin/env python3
"""应用配置管理（晴川 x-QingChuan，对齐北辰 core/config 分段口径）。

配置来源与优先级：环境变量 > .env > 代码默认值。
分段配置各自带独立环境变量前缀（如 QINGCHUAN_AGENT_LOGGING_LEVEL），
避免扁平面板式配置散落；配置非法直接阻断启动（validate）。

Usage:
    from qingchuan_agent.core.config import settings
    level = settings.logging.level
    db_url = settings.database.url
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final
from urllib.parse import quote_plus

from dotenv import dotenv_values
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from qingchuan_agent.constants import Environment, RouteMode

# 仓库根 .env（本地开发单一配置源；任意 CWD 启动均能加载）
QINGCHUAN_ROOT_ENV: Final[Path] = Path(__file__).resolve().parents[5] / ".env"


class LoggingSettings(BaseSettings):
    """日志配置。"""

    model_config = SettingsConfigDict(env_prefix="QINGCHUAN_AGENT_LOGGING_", extra="ignore")

    level: str = "INFO"
    format: str = "console"  # "json" | "console"
    # 与 rag-service 保持一致：相对路径由 logger 按服务根目录（src 的上级目录）解析，
    # 任意 CWD 启动均落位 apps/agent-service/logs/，文件名 x-QingChuan-{time:YYYYMMDDHHmmss}.log
    file_path: str = "./logs/x-QingChuan-{time:YYYYMMDDHHmmss}.log"
    rotation: str = "1 day"
    retention: str = "7 days"
    compression: str = "zip"
    console_output: bool = True


class ServerSettings(BaseSettings):
    """HTTP 服务配置（uvicorn 监听）。"""

    model_config = SettingsConfigDict(env_prefix="QINGCHUAN_AGENT_SERVER_", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8020
    debug: bool = True
    workers: int = 1


class CorsSettings(BaseSettings):
    """跨域配置。"""

    model_config = SettingsConfigDict(env_prefix="QINGCHUAN_AGENT_CORS_", extra="ignore")

    enabled: bool = True
    origins: list[str] = ["*"]
    allow_credentials: bool = True
    allow_methods: list[str] = ["*"]
    allow_headers: list[str] = ["*"]


class DatabaseSettings(BaseSettings):
    """数据库配置（Agent 任务 / 事件持久化；骨架阶段默认关闭，可无库启动）。"""

    model_config = SettingsConfigDict(env_prefix="QINGCHUAN_AGENT_DATABASE_", extra="ignore")

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


class AiLLMSettings(BaseSettings):
    """大模型配置（LangChain ChatOpenAI 兼容接口；骨架阶段不配 key 走 Mock）。"""

    model_config = SettingsConfigDict(extra="ignore")

    base_url: str = ""
    api_key: str = ""  # 敏感信息，仅通过环境变量 / .env 注入
    model: str = "deepseek-chat"
    temperature: float = 0.7
    max_tokens: int = 2048
    timeout_seconds: int = 60


class AiSettings(BaseSettings):
    """AI 整体配置（本期骨架：LLM 预留，节点内业务为 mock）。"""

    model_config = SettingsConfigDict(env_prefix="QINGCHUAN_AGENT_AI_", extra="ignore")

    enabled: bool = True
    llm: AiLLMSettings = AiLLMSettings()


class AgentSettings(BaseSettings):
    """Agent 编排配置（调度中枢 / 子图 / 任务状态机）。"""

    model_config = SettingsConfigDict(env_prefix="QINGCHUAN_AGENT_AGENT_", extra="ignore")

    route_mode: str = RouteMode.EXPLICIT.mark  # explicit / llm / hybrid
    checkpoint: str = "memory"  # memory / redis（redis 待接入）
    confidence_threshold: float = 0.7  # LLM 动态路由采信阈值
    task_max_retries: int = 3  # 失败重试上限
    task_timeout_seconds: int = 300  # 单任务超时


class RagClientSettings(BaseSettings):
    """rag-service 客户端配置（MCP 优先，HTTP 兜底）。"""

    model_config = SettingsConfigDict(env_prefix="QINGCHUAN_AGENT_RAG_", extra="ignore")

    # MCP 主链路：rag-service 以 streamable HTTP 挂载 /mcp（见 rag-service main.py），
    # agent 经 qingchuan_common.mcp.MCPClient 连接调用 retrieve_docs / rag_query
    mcp_url: str = "http://rag-service:8010/mcp"
    # HTTP 兜底链路（预留：MCP 不可用时降级调 /api/v1/rag/*，当前未实现）
    http_base_url: str = "http://rag-service:8010"
    mcp_timeout_seconds: float = 60.0


class Settings(BaseSettings):
    """Agent 服务全局配置（分段：server / logging / cors / database / ai / agent / rag）。"""

    model_config = SettingsConfigDict(
        env_prefix="QINGCHUAN_AGENT_",
        env_file=str(QINGCHUAN_ROOT_ENV),
        extra="ignore",
    )

    app_env: str = Environment.DEVELOPMENT.mark
    service_name: str = "agent-service"

    server: ServerSettings = ServerSettings()
    logging: LoggingSettings = LoggingSettings()
    cors: CorsSettings = CorsSettings()
    database: DatabaseSettings = DatabaseSettings()
    ai: AiSettings = AiSettings()
    agent: AgentSettings = AgentSettings()
    rag: RagClientSettings = RagClientSettings()

    @model_validator(mode="after")
    def _load_database_from_env_file(self) -> Settings:
        """从 .env 补齐 database 段（pydantic-settings 的 env_file 不作用于嵌套模型字段）。

        优先级：OS 环境变量 > .env > 代码默认值。仅当 OS 环境未提供对应变量时，
        才从 .env 取数，避免覆盖部署环境注入的配置。
        """
        values = dotenv_values(QINGCHUAN_ROOT_ENV)
        if not values:
            return self
        prefix = "QINGCHUAN_AGENT_DATABASE_"
        overrides: dict[str, object] = {}
        for field in ("enabled", "host", "port", "user", "password", "database"):
            env_key = prefix + field.upper()
            if env_key in values and env_key not in os.environ:
                overrides[field] = values[env_key]
        if overrides:
            merged = self.database.model_dump()
            merged.update(overrides)
            self.database = DatabaseSettings(**merged)
        return self

    @model_validator(mode="after")
    def _load_rag_from_env_file(self) -> Settings:
        """从 .env 补齐 rag 段（嵌套模型字段不自动读取 env_file，与 database 段同因）。"""
        values = dotenv_values(QINGCHUAN_ROOT_ENV)
        if not values:
            return self
        prefix = "QINGCHUAN_AGENT_RAG_"
        overrides: dict[str, object] = {}
        for field in ("mcp_url", "http_base_url", "mcp_timeout_seconds"):
            env_key = prefix + field.upper()
            if env_key in values and env_key not in os.environ:
                overrides[field] = values[env_key]
        if overrides:
            merged = self.rag.model_dump()
            merged.update(overrides)
            self.rag = RagClientSettings(**merged)
        return self

    @model_validator(mode="after")
    def _load_ai_from_env(self) -> Settings:
        """从 OS 环境变量与 .env 补齐 ai.llm 段。

        与 database / rag 段同因：pydantic-settings 的 env_file 不作用于嵌套模型字段。
        区别在于 ai.llm 是两级嵌套（Settings.ai.llm），连 OS 环境变量的两级前缀
        也不会被 pydantic 组装读取，因此这里同时兜住 os.environ 与 .env。
        优先级：OS 环境变量 > .env > 代码默认值（OS 已注入时不再用 .env 覆盖）。
        """
        prefix = "QINGCHUAN_AGENT_AI_LLM_"
        os_values = {k: v for k, v in os.environ.items() if k.startswith(prefix)}
        file_values = dotenv_values(QINGCHUAN_ROOT_ENV)
        overrides: dict[str, object] = {}
        for field in (
            "base_url",
            "api_key",
            "model",
            "temperature",
            "max_tokens",
            "timeout_seconds",
        ):
            env_key = prefix + field.upper()
            raw = os_values.get(env_key, file_values.get(env_key))
            if raw is None:
                continue
            try:
                if field == "temperature":
                    overrides[field] = float(raw)
                elif field in ("max_tokens", "timeout_seconds"):
                    overrides[field] = int(raw)
                else:
                    overrides[field] = str(raw)
            except (ValueError, TypeError):
                pass
        if overrides:
            merged = self.ai.llm.model_dump()
            merged.update(overrides)
            self.ai.llm = AiLLMSettings(**merged)
        return self

    # ----------------------------------------------------------
    # 环境判断
    # ----------------------------------------------------------

    @property
    def is_development(self) -> bool:
        return self.app_env == Environment.DEVELOPMENT.mark

    @property
    def is_production(self) -> bool:
        return self.app_env == Environment.PRODUCTION.mark

    # ----------------------------------------------------------
    # 配置校验
    # ----------------------------------------------------------

    def validate(self) -> None:
        """验证配置合法性，配置错误直接阻断启动。"""
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
            if self.agent.checkpoint == "memory":
                raise ValueError(
                    "生产环境（APP_ENV=production）禁止使用 memory checkpoint，请配置 redis"
                )


# ============================================================
# 全局单例（导入即加载并校验，配置错误直接阻断启动）
# ============================================================
settings: Final[Settings] = Settings()
settings.validate()


def get_settings() -> Settings:
    """获取全局配置单例。"""
    return settings


__all__ = [
    "AgentSettings",
    "AiLLMSettings",
    "AiSettings",
    "CorsSettings",
    "DatabaseSettings",
    "LoggingSettings",
    "RagClientSettings",
    "ServerSettings",
    "Settings",
    "get_settings",
    "settings",
]
