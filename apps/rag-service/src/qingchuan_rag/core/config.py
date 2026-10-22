#!/usr/bin/env python3
"""
Settings Configuration Module

全局配置中心
支持从环境变量和YAML配置文件读取配置

NOTE: 默认值统一从 constants/ 模块引用，避免重复定义
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

import yaml
from dotenv import load_dotenv

from qingchuan_rag.constants import (
    API_PREFIX,
    APP_DESCRIPTION,
    APP_ID,
    APP_NAME,
    APP_VERSION,
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_CONFIG_FILE,
    DEFAULT_EMBEDDING_BATCH_SIZE,
    DEFAULT_EMBEDDING_CACHE_SIZE,
    DEFAULT_EMBEDDING_DEVICE,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MMR_LAMBDA,
    DEFAULT_SIMILARITY_THRESHOLD,
    DEFAULT_TEMPERATURE,
    DEFAULT_TIMEOUT,
    DEFAULT_TOP_K,
)

# 仓库根 .env（本地开发单一配置源；任意 CWD 启动均能加载，避免 .env 相对 CWD 失效）
QINGCHUAN_ROOT_ENV: Final[Path] = Path(__file__).resolve().parents[5] / ".env"


@dataclass
class ServerConfig:
    """服务器配置"""

    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True
    workers: int = 4
    environment: str = "development"


@dataclass
class LoggingConfig:
    """日志配置"""

    level: str = "INFO"
    file_path: str = "./logs/x-QingChuan-{time:YYYYMMDDHHmmss}.log"
    rotation: str = "1 day"
    retention: str = "7 days"


@dataclass
class RateLimitConfig:
    """限流配置"""

    enabled: bool = False
    requests_per_minute: int = 60
    requests_per_hour: int = 1000


@dataclass
class CORSConfig:
    """CORS配置"""

    enabled: bool = True
    allow_origins: list[str] = field(default_factory=lambda: ["*"])
    allow_credentials: bool = True
    allow_methods: list[str] = field(
        default_factory=lambda: ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    )
    allow_headers: list[str] = field(default_factory=lambda: ["*"])


@dataclass
class DatabaseConfig:
    """业务数据库配置（审计日志等业务表落 MySQL，本地开发可回退 SQLite）"""

    db_url: str = "mysql+pymysql://yeyushilai:123456@localhost:3306/qingchuan?charset=utf8mb4"


@dataclass
class SyncConfig:
    """人社数据同步配置（触发接口 + 内置周期调度）

    数据源接口层在 qingchuan_rag/infras/hrss.py（依赖 infras/http.py），
    接入真实接口后主要调整 HRSS_API_URL / HRSS_API_TOKEN / HRSS_MOCK。
    """

    enabled: bool = False
    cron: str = "0 3 * * *"
    batch_size: int = 100
    incremental: bool = True
    # 人社数据源（生产必填；细节见 qingchuan_rag/infras/hrss.py）
    data_source_url: str = ""
    data_source_token: str = ""
    data_source_timeout: float = 30.0
    # mock 模式：无真实 API 时返回本地示例数据，便于端到端调试同步链路
    data_source_mock: bool = True
    data_source_mock_count: int = 5


@dataclass
class EmbeddingConfig:
    """向量模型配置"""

    model: str = DEFAULT_EMBEDDING_MODEL
    device: str = DEFAULT_EMBEDDING_DEVICE
    batch_size: int = DEFAULT_EMBEDDING_BATCH_SIZE
    normalize: bool = True
    cache_size: int = DEFAULT_EMBEDDING_CACHE_SIZE


@dataclass
class VectorStoreConfig:
    """向量存储配置

    type: chroma | milvus
        - chroma：本地持久化目录（persist_directory），开发默认
        - milvus：本地 milvus-lite 文件（milvus_uri="./data/milvus.db"）或远程 Milvus 服务
          （milvus_uri="http://milvus:19530"）；dimension 用于建集合（缺省时按首条向量自动推导）
    """

    type: str = "chroma"
    persist_directory: str = "./data/chroma"
    collection_name: str = "documents"
    distance: str = "cosine"
    milvus_uri: str = "./data/milvus.db"
    dimension: int | None = None


@dataclass
class TextSplitterConfig:
    """文本切分配置"""

    provider: str = "langchain"
    strategy: str = "recursive"
    chunk_size: int = DEFAULT_CHUNK_SIZE
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP
    separators: list[str] = field(default_factory=lambda: ["\n\n", "\n", "。", "！", "？", " ", ""])


@dataclass
class RetrievalConfig:
    """检索配置"""

    top_k: int = DEFAULT_TOP_K
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD
    use_mmr: bool = False
    mmr_lambda: float = DEFAULT_MMR_LAMBDA


@dataclass
class GenerationConfig:
    """生成配置"""

    provider: str = "mimo"
    model: str = "mimo-v2.6-pro"
    temperature: float = DEFAULT_TEMPERATURE
    max_tokens: int = DEFAULT_MAX_TOKENS
    timeout: int = DEFAULT_TIMEOUT


@dataclass
class StorageConfig:
    """文件存储配置（文档内容对象存储，元数据入库后内容走此层）。

    provider: local | s3
        - local：本地文件系统（开发 / 单机生产默认，相对路径锚定服务根 data 目录）
        - s3：S3 兼容对象存储（MinIO / 阿里云 OSS / 腾讯 COS / 七牛 Kodo，生产推荐）
    """

    provider: str = "local"
    # local
    base_dir: str = "./data/documents"
    public_prefix: str = "/files"
    # s3（S3 兼容对象存储）
    s3_endpoint_url: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_bucket: str = ""
    s3_region: str = ""
    s3_prefix: str = "documents"
    s3_public_url: str = ""
    s3_use_ssl: bool = True


@dataclass
class LLMDefaultsConfig:
    """LLM 调用层通用默认配置（所有 Provider 的兜底参数，独立于 RAG 生成配置）"""

    max_tokens: int = DEFAULT_MAX_TOKENS
    timeout: int = DEFAULT_TIMEOUT


@dataclass
class LLMProvidersConfig:
    """LLM 提供商配置"""

    # DeepSeek
    deepseek_api_key: str = ""
    deepseek_api_base: str = "https://api.deepseek.com/v1"
    deepseek_model_name: str = "deepseek-chat"
    # 豆包
    doubao_api_key: str = ""
    doubao_api_base: str = ""
    doubao_model_name: str = "doubao-pro-32k"
    # 阿里云百炼
    aliyun_api_key: str = ""
    aliyun_api_base: str = ""
    aliyun_model_name: str = "qwen-plus"
    # 小米 Mimo
    mimo_api_key: str = ""
    mimo_api_base: str = "https://api.xiaomimimo.com/v1"
    mimo_model_name: str = "mimo-v2.6-pro"


class Settings:
    """应用配置类

    支持从环境变量和YAML配置文件读取配置
    优先级：环境变量 > YAML配置文件 > 默认配置
    """

    CONFIG_FILE_PATH: Final[str] = DEFAULT_CONFIG_FILE

    def __init__(self) -> None:
        """初始化配置"""
        load_dotenv(QINGCHUAN_ROOT_ENV)
        self._config: dict[str, Any] = self._load_config()
        self._parse_config()

    def _get_default_config(self) -> dict[str, Any]:
        """获取默认配置"""
        return {
            "server": {
                "host": "0.0.0.0",
                "port": 8010,
                "debug": True,
                "workers": 4,
                "environment": "development",
            },
            "logging": {
                "level": "INFO",
                "file_path": "./logs/x-QingChuan-{time:YYYYMMDDHHmmss}.log",
                "rotation": "1 day",
                "retention": "7 days",
            },
            "database": {
                "db_url": "mysql+pymysql://yeyushilai:123456@localhost:3306/qingchuan?charset=utf8mb4",
            },
            "sync": {
                "enabled": False,
                "cron": "0 3 * * *",
                "batch_size": 100,
                "incremental": True,
                "data_source_url": "",
                "data_source_token": "",
            },
            "rate_limit": {
                "enabled": False,
                "requests_per_minute": 60,
                "requests_per_hour": 1000,
            },
            "cors": {
                "enabled": True,
                "allow_origins": ["*"],
                "allow_credentials": True,
                "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                "allow_headers": ["*"],
            },
            "embedding": {
                "model": DEFAULT_EMBEDDING_MODEL,
                "device": DEFAULT_EMBEDDING_DEVICE,
                "batch_size": DEFAULT_EMBEDDING_BATCH_SIZE,
                "normalize": True,
                "cache_size": DEFAULT_EMBEDDING_CACHE_SIZE,
            },
            "vector_store": {
                "type": "chroma",
                "persist_directory": "./data/chroma",
                "collection_name": "documents",
                "distance": "cosine",
                "milvus_uri": "./data/milvus.db",
                "dimension": None,
            },
            "storage": {
                "provider": "local",
                "base_dir": "./data/documents",
                "public_prefix": "/files",
                "s3_endpoint_url": "",
                "s3_access_key": "",
                "s3_secret_key": "",
                "s3_bucket": "",
                "s3_region": "",
                "s3_prefix": "documents",
                "s3_public_url": "",
                "s3_use_ssl": True,
            },
            "text_splitter": {
                "provider": "langchain",
                "strategy": "recursive",
                "chunk_size": DEFAULT_CHUNK_SIZE,
                "chunk_overlap": DEFAULT_CHUNK_OVERLAP,
                "separators": ["\n\n", "\n", "。", "！", "？", " ", ""],
            },
            "retrieval": {
                "top_k": DEFAULT_TOP_K,
                "similarity_threshold": DEFAULT_SIMILARITY_THRESHOLD,
                "use_mmr": False,
                "mmr_lambda": DEFAULT_MMR_LAMBDA,
            },
            "generation": {
                "provider": "mimo",
                "model": "mimo-v2.6-pro",
                "temperature": DEFAULT_TEMPERATURE,
                "max_tokens": DEFAULT_MAX_TOKENS,
                "timeout": DEFAULT_TIMEOUT,
            },
            "llm": {
                "max_tokens": DEFAULT_MAX_TOKENS,
                "timeout": DEFAULT_TIMEOUT,
            },
            "llm_providers": {
                "deepseek_api_key": "",
                "deepseek_api_base": "https://api.deepseek.com/v1",
                "deepseek_model_name": "deepseek-chat",
                "doubao_api_key": "",
                "doubao_api_base": "",
                "doubao_model_name": "doubao-pro-32k",
                "aliyun_api_key": "",
                "aliyun_api_base": "",
                "aliyun_model_name": "qwen-plus",
                "mimo_api_key": "",
                "mimo_api_base": "https://api.xiaomimimo.com/v1",
                "mimo_model_name": "mimo-v2.6-pro",
            },
        }

    def _load_config(self) -> dict[str, Any]:
        """加载配置

        优先级：环境变量 > YAML配置文件 > 默认配置
        """
        config: dict[str, Any] = self._get_default_config()
        self._load_from_file(config)
        self._load_from_env(config)
        return config

    def _load_from_file(self, config: dict[str, Any]) -> None:
        """从YAML文件加载配置"""
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

    def _load_from_env(self, config: dict[str, Any]) -> None:
        """从环境变量加载配置"""
        env_mappings = {
            "DEBUG": ("server", "debug", lambda v: v.lower() == "true"),
            "PORT": ("server", "port", int),
            "SERVER_PORT": ("server", "port", int),
            "SERVER_HOST": ("server", "host", str),
            "SERVER_WORKERS": ("server", "workers", int),
            "SERVER_ENVIRONMENT": ("server", "environment", str),
            "LOG_LEVEL": ("logging", "level", str),
            "LOG_FILE_PATH": ("logging", "file_path", str),
            "LOG_ROTATION": ("logging", "rotation", str),
            "LOG_RETENTION": ("logging", "retention", str),
            "EMBEDDING_MODEL": ("embedding", "model", str),
            "EMBEDDING_DEVICE": ("embedding", "device", str),
            "EMBEDDING_BATCH_SIZE": ("embedding", "batch_size", int),
            "EMBEDDING_NORMALIZE": ("embedding", "normalize", lambda v: v.lower() == "true"),
            "EMBEDDING_CACHE_SIZE": ("embedding", "cache_size", int),
            "VECTOR_STORE_TYPE": ("vector_store", "type", str),
            "VECTOR_STORE_PERSIST_DIR": ("vector_store", "persist_directory", str),
            "VECTOR_STORE_COLLECTION_NAME": ("vector_store", "collection_name", str),
            "VECTOR_STORE_DISTANCE": ("vector_store", "distance", str),
            # .env 统一使用 VECTOR_STORE_MILVUS_URI 前缀（避免与 pymilvus 保留的 MILVUS_URI 环境变量冲突）
            "VECTOR_STORE_MILVUS_URI": ("vector_store", "milvus_uri", str),
            "VECTOR_STORE_DIMENSION": ("vector_store", "dimension", int),
            "TEXT_SPLITTER_PROVIDER": ("text_splitter", "provider", str),
            "TEXT_SPLITTER_STRATEGY": ("text_splitter", "strategy", str),
            "TEXT_SPLITTER_CHUNK_SIZE": ("text_splitter", "chunk_size", int),
            "TEXT_SPLITTER_CHUNK_OVERLAP": ("text_splitter", "chunk_overlap", int),
            "RETRIEVAL_TOP_K": ("retrieval", "top_k", int),
            "RETRIEVAL_SIMILARITY_THRESHOLD": ("retrieval", "similarity_threshold", float),
            "RETRIEVAL_USE_MMR": ("retrieval", "use_mmr", lambda v: v.lower() == "true"),
            "RETRIEVAL_MMR_LAMBDA": ("retrieval", "mmr_lambda", float),
            "GENERATION_PROVIDER": ("generation", "provider", str),
            "GENERATION_MODEL": ("generation", "model", str),
            "GENERATION_TEMPERATURE": ("generation", "temperature", float),
            "GENERATION_MAX_TOKENS": ("generation", "max_tokens", int),
            "GENERATION_TIMEOUT": ("generation", "timeout", int),
            # LLM 调用层通用默认
            "LLM_MAX_TOKENS": ("llm", "max_tokens", int),
            "LLM_TIMEOUT": ("llm", "timeout", int),
            # DeepSeek
            "DEEPSEEK_API_KEY": ("llm_providers", "deepseek_api_key", str),
            "DEEPSEEK_API_BASE": ("llm_providers", "deepseek_api_base", str),
            "DEEPSEEK_MODEL_NAME": ("llm_providers", "deepseek_model_name", str),
            # 豆包
            "DOUBAO_API_KEY": ("llm_providers", "doubao_api_key", str),
            "DOUBAO_API_BASE": ("llm_providers", "doubao_api_base", str),
            "DOUBAO_MODEL_NAME": ("llm_providers", "doubao_model_name", str),
            # 阿里云百炼
            "ALIYUN_API_KEY": ("llm_providers", "aliyun_api_key", str),
            "ALIYUN_API_BASE": ("llm_providers", "aliyun_api_base", str),
            "ALIYUN_MODEL_NAME": ("llm_providers", "aliyun_model_name", str),
            # 小米 Mimo
            "MIMO_API_KEY": ("llm_providers", "mimo_api_key", str),
            "MIMO_API_BASE": ("llm_providers", "mimo_api_base", str),
            "MIMO_MODEL_NAME": ("llm_providers", "mimo_model_name", str),
            "RATE_LIMIT_ENABLED": ("rate_limit", "enabled", lambda v: v.lower() == "true"),
            "RATE_LIMIT_REQUESTS_PER_MINUTE": ("rate_limit", "requests_per_minute", int),
            "RATE_LIMIT_REQUESTS_PER_HOUR": ("rate_limit", "requests_per_hour", int),
            "CORS_ENABLED": ("cors", "enabled", lambda v: v.lower() == "true"),
            "CORS_ALLOW_ORIGINS": ("cors", "allow_origins", str),
            "CORS_ALLOW_CREDENTIALS": ("cors", "allow_credentials", lambda v: v.lower() == "true"),
            "CORS_ALLOW_METHODS": ("cors", "allow_methods", str),
            "CORS_ALLOW_HEADERS": ("cors", "allow_headers", str),
            # 业务数据库（审计日志 / 同步任务 / 文档元数据）
            "DATABASE_URL": ("database", "db_url", str),
            # 文件存储（文档内容对象存储）
            "STORAGE_PROVIDER": ("storage", "provider", str),
            "STORAGE_LOCAL_BASE_DIR": ("storage", "base_dir", str),
            "STORAGE_LOCAL_PUBLIC_PREFIX": ("storage", "public_prefix", str),
            "STORAGE_S3_ENDPOINT_URL": ("storage", "s3_endpoint_url", str),
            "STORAGE_S3_ACCESS_KEY": ("storage", "s3_access_key", str),
            "STORAGE_S3_SECRET_KEY": ("storage", "s3_secret_key", str),
            "STORAGE_S3_BUCKET": ("storage", "s3_bucket", str),
            "STORAGE_S3_REGION": ("storage", "s3_region", str),
            "STORAGE_S3_PREFIX": ("storage", "s3_prefix", str),
            "STORAGE_S3_PUBLIC_URL": ("storage", "s3_public_url", str),
            "STORAGE_S3_USE_SSL": ("storage", "s3_use_ssl", lambda v: v.lower() == "true"),
            # 人社数据同步
            "SYNC_ENABLED": ("sync", "enabled", lambda v: v.lower() == "true"),
            "SYNC_CRON": ("sync", "cron", str),
            "SYNC_BATCH_SIZE": ("sync", "batch_size", int),
            "SYNC_INCREMENTAL": ("sync", "incremental", lambda v: v.lower() == "true"),
            "HRSS_API_URL": ("sync", "data_source_url", str),
            "HRSS_API_TOKEN": ("sync", "data_source_token", str),
            "HRSS_API_TIMEOUT": ("sync", "data_source_timeout", float),
            "HRSS_MOCK": ("sync", "data_source_mock", lambda v: v.lower() == "true"),
            "HRSS_MOCK_COUNT": ("sync", "data_source_mock_count", int),
        }

        for env_key, (section, field_key, converter) in env_mappings.items():
            env_value = os.environ.get(env_key)
            if env_value is not None:
                try:
                    config[section][field_key] = converter(env_value)
                except (ValueError, TypeError):
                    pass

    def _parse_config(self) -> None:
        """解析配置到具体配置对象"""
        self.server = ServerConfig(**self._config["server"])
        self.logging = LoggingConfig(**self._config["logging"])
        self.rate_limit = RateLimitConfig(**self._config["rate_limit"])
        self.cors = CORSConfig(**self._config["cors"])
        self.database = DatabaseConfig(**self._config["database"])
        self.sync = SyncConfig(**self._config["sync"])
        self.storage = StorageConfig(**self._config["storage"])
        self.embedding = EmbeddingConfig(**self._config["embedding"])
        self.vector_store = VectorStoreConfig(**self._config["vector_store"])
        self.text_splitter = TextSplitterConfig(**self._config["text_splitter"])
        self.retrieval = RetrievalConfig(**self._config["retrieval"])
        self.generation = GenerationConfig(**self._config["generation"])
        self.llm = LLMDefaultsConfig(**self._config["llm"])
        self.llm_providers = LLMProvidersConfig(**self._config["llm_providers"])

    def reload(self) -> None:
        """重新加载配置"""
        self._config = self._load_config()
        self._parse_config()

    # === 属性快捷方式 ===
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

    @property
    def SERVER_ENVIRONMENT(self) -> str:
        return self.server.environment

    @property
    def LOG_LEVEL(self) -> str:
        return self.logging.level

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
    def EMBEDDING_MODEL(self) -> str:
        return self.embedding.model

    @property
    def EMBEDDING_DEVICE(self) -> str:
        return self.embedding.device

    @property
    def EMBEDDING_BATCH_SIZE(self) -> int:
        return self.embedding.batch_size

    @property
    def EMBEDDING_NORMALIZE(self) -> bool:
        return self.embedding.normalize

    @property
    def EMBEDDING_CACHE_SIZE(self) -> int:
        return self.embedding.cache_size

    @property
    def VECTOR_STORE_PERSIST_DIR(self) -> str:
        return self.vector_store.persist_directory

    @property
    def VECTOR_STORE_COLLECTION_NAME(self) -> str:
        return self.vector_store.collection_name

    @property
    def VECTOR_STORE_DISTANCE(self) -> str:
        return self.vector_store.distance

    @property
    def VECTOR_STORE_TYPE(self) -> str:
        return self.vector_store.type

    @property
    def VECTOR_STORE_MILVUS_URI(self) -> str:
        return self.vector_store.milvus_uri

    @property
    def VECTOR_STORE_DIMENSION(self) -> int | None:
        return self.vector_store.dimension

    @property
    def TEXT_SPLITTER_PROVIDER(self) -> str:
        return self.text_splitter.provider

    @property
    def TEXT_SPLITTER_STRATEGY(self) -> str:
        return self.text_splitter.strategy

    @property
    def TEXT_SPLITTER_CHUNK_SIZE(self) -> int:
        return self.text_splitter.chunk_size

    @property
    def TEXT_SPLITTER_CHUNK_OVERLAP(self) -> int:
        return self.text_splitter.chunk_overlap

    @property
    def TEXT_SPLITTER_SEPARATORS(self) -> list[str]:
        return self.text_splitter.separators

    @property
    def RETRIEVAL_TOP_K(self) -> int:
        return self.retrieval.top_k

    @property
    def RETRIEVAL_SIMILARITY_THRESHOLD(self) -> float:
        return self.retrieval.similarity_threshold

    @property
    def RETRIEVAL_USE_MMR(self) -> bool:
        return self.retrieval.use_mmr

    @property
    def RETRIEVAL_MMR_LAMBDA(self) -> float:
        return self.retrieval.mmr_lambda

    @property
    def GENERATION_PROVIDER(self) -> str:
        return self.generation.provider

    @property
    def GENERATION_MODEL(self) -> str:
        return self.generation.model

    @property
    def GENERATION_TEMPERATURE(self) -> float:
        return self.generation.temperature

    @property
    def GENERATION_MAX_TOKENS(self) -> int:
        return self.generation.max_tokens

    @property
    def GENERATION_TIMEOUT(self) -> int:
        return self.generation.timeout

    # ===== LLM 调用层通用默认 =====
    @property
    def LLM_MAX_TOKENS(self) -> int:
        return self.llm.max_tokens

    @property
    def LLM_TIMEOUT(self) -> int:
        return self.llm.timeout

    # ===== LLM Provider Settings =====
    @property
    def DEEPSEEK_API_KEY(self) -> str:
        return self.llm_providers.deepseek_api_key

    @property
    def DEEPSEEK_API_BASE(self) -> str:
        return self.llm_providers.deepseek_api_base

    @property
    def DEEPSEEK_MODEL_NAME(self) -> str:
        return self.llm_providers.deepseek_model_name

    @property
    def DOUBAO_API_KEY(self) -> str:
        return self.llm_providers.doubao_api_key

    @property
    def DOUBAO_API_BASE(self) -> str:
        return self.llm_providers.doubao_api_base

    @property
    def DOUBAO_MODEL_NAME(self) -> str:
        return self.llm_providers.doubao_model_name

    @property
    def ALIYUN_API_KEY(self) -> str:
        return self.llm_providers.aliyun_api_key

    @property
    def ALIYUN_API_BASE(self) -> str:
        return self.llm_providers.aliyun_api_base

    @property
    def ALIYUN_MODEL_NAME(self) -> str:
        return self.llm_providers.aliyun_model_name

    @property
    def MIMO_API_KEY(self) -> str:
        return self.llm_providers.mimo_api_key

    @property
    def MIMO_API_BASE(self) -> str:
        return self.llm_providers.mimo_api_base

    @property
    def MIMO_MODEL_NAME(self) -> str:
        return self.llm_providers.mimo_model_name

    # Legacy aliases for compatibility
    @property
    def TEMPERATURE(self) -> float:
        return self.generation.temperature

    @property
    def API_PREFIX(self) -> str:
        return API_PREFIX

    # 应用信息（对应 constants.APP_ID/APP_NAME/APP_DESCRIPTION/APP_VERSION，不再从配置读取）
    @property
    def APP_ID(self) -> str:
        return APP_ID

    @property
    def APP_NAME(self) -> str:
        return APP_NAME

    @property
    def APP_DESCRIPTION(self) -> str:
        return APP_DESCRIPTION

    @property
    def APP_VERSION(self) -> str:
        return APP_VERSION

    @property
    def RATE_LIMIT_ENABLED(self) -> bool:
        return self.rate_limit.enabled

    @property
    def RATE_LIMIT_REQUESTS_PER_MINUTE(self) -> int:
        return self.rate_limit.requests_per_minute

    @property
    def RATE_LIMIT_REQUESTS_PER_HOUR(self) -> int:
        return self.rate_limit.requests_per_hour

    @property
    def CORS_ENABLED(self) -> bool:
        return self.cors.enabled

    @property
    def CORS_ALLOW_ORIGINS(self) -> str:
        if isinstance(self.cors.allow_origins, list):
            return ",".join(self.cors.allow_origins)
        return self.cors.allow_origins

    @property
    def CORS_ALLOW_METHODS(self) -> list[str]:
        return self.cors.allow_methods

    @property
    def CORS_ALLOW_HEADERS(self) -> list[str]:
        return self.cors.allow_headers

    # ===== 业务数据库 =====
    @property
    def DATABASE_URL(self) -> str:
        return self.database.db_url

    # ===== 文件存储（文档内容对象存储） =====
    @property
    def STORAGE_PROVIDER(self) -> str:
        return self.storage.provider

    @property
    def STORAGE_LOCAL_BASE_DIR(self) -> str:
        return self.storage.base_dir

    @property
    def STORAGE_LOCAL_PUBLIC_PREFIX(self) -> str:
        return self.storage.public_prefix

    @property
    def STORAGE_S3_ENDPOINT_URL(self) -> str:
        return self.storage.s3_endpoint_url

    @property
    def STORAGE_S3_ACCESS_KEY(self) -> str:
        return self.storage.s3_access_key

    @property
    def STORAGE_S3_SECRET_KEY(self) -> str:
        return self.storage.s3_secret_key

    @property
    def STORAGE_S3_BUCKET(self) -> str:
        return self.storage.s3_bucket

    @property
    def STORAGE_S3_REGION(self) -> str:
        return self.storage.s3_region

    @property
    def STORAGE_S3_PREFIX(self) -> str:
        return self.storage.s3_prefix

    @property
    def STORAGE_S3_PUBLIC_URL(self) -> str:
        return self.storage.s3_public_url

    @property
    def STORAGE_S3_USE_SSL(self) -> bool:
        return self.storage.s3_use_ssl

    # ===== 人社数据同步 =====
    @property
    def SYNC_ENABLED(self) -> bool:
        return self.sync.enabled

    @property
    def SYNC_CRON(self) -> str:
        return self.sync.cron

    @property
    def SYNC_BATCH_SIZE(self) -> int:
        return self.sync.batch_size

    @property
    def SYNC_INCREMENTAL(self) -> bool:
        return self.sync.incremental

    @property
    def HRSS_API_URL(self) -> str:
        return self.sync.data_source_url

    @property
    def HRSS_API_TOKEN(self) -> str:
        return self.sync.data_source_token

    @property
    def HRSS_API_TIMEOUT(self) -> float:
        return self.sync.data_source_timeout

    @property
    def HRSS_MOCK(self) -> bool:
        return self.sync.data_source_mock

    @property
    def HRSS_MOCK_COUNT(self) -> int:
        return self.sync.data_source_mock_count


# 创建全局配置实例
settings: Final[Settings] = Settings()

__all__ = [
    "ServerConfig",
    "LoggingConfig",
    "RateLimitConfig",
    "CORSConfig",
    "DatabaseConfig",
    "SyncConfig",
    "EmbeddingConfig",
    "VectorStoreConfig",
    "TextSplitterConfig",
    "RetrievalConfig",
    "GenerationConfig",
    "LLMProvidersConfig",
    "Settings",
    "settings",
]
