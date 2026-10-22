#!/usr/bin/env python3
"""数据库基础设施（SQLAlchemy 2.0）。

以 Provider 抽象封装数据库后端，业务层只依赖 DatabaseProvider 抽象：
- MySqlProvider：默认后端（生产形态，连接池 + 北京时间统一）；
- SqliteProvider：回退后端（本地开发 / 单机部署，零外部依赖启动）。

切换方式：DATABASE_URL 的 scheme 决定实现——
    mysql://  → MySqlProvider
    sqlite:// → SqliteProvider
新增其他数据库后端只需实现 DatabaseProvider 并注册到 _build_provider。
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from collections.abc import Generator, Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from qingchuan_rag.core.config import settings
from qingchuan_rag.core.logger import logger
from qingchuan_rag.core.paths import SERVICE_ROOT


class Base(DeclarativeBase):
    """ORM 声明式基类（SQLAlchemy 2.0 风格）。"""


def _anchor_sqlite_url(database_url: str) -> str:
    """将相对路径的 sqlite URL 锚定到服务根目录（sqlite:///./data/x.db → sqlite:///<服务根>/data/x.db）。

    - sqlite:///:memory: 等内存库、绝对路径、其他 scheme 原样返回。
    """
    if not database_url.startswith("sqlite:///"):
        return database_url
    rest = database_url[len("sqlite:///") :]
    if not rest or rest.startswith(":") or os.path.isabs(rest):
        return database_url
    return f"sqlite:///{SERVICE_ROOT / rest}"


# ============================================================
# 数据库后端抽象
# ============================================================
class DatabaseProvider(ABC):
    """数据库提供者抽象接口。

    所有数据库后端必须实现此接口；业务层仅依赖此抽象，
    切换数据库实现只需修改配置（DATABASE_URL），无需改动业务代码。
    """

    @abstractmethod
    def get_engine(self) -> Engine:
        """获取数据库引擎。"""

    @abstractmethod
    def get_session_factory(self) -> sessionmaker[Session]:
        """获取会话工厂。"""

    @abstractmethod
    @contextmanager
    def session(self) -> Iterator[Session]:
        """获取数据库会话的上下文管理器（自动提交 / 回滚 / 关闭）。"""

    @abstractmethod
    def check_connection(self) -> bool:
        """检测数据库连接是否可用。"""

    @abstractmethod
    def close(self) -> None:
        """关闭连接池，释放资源。"""


# ============================================================
# MySQL 实现（默认后端）
# ============================================================
class MySqlProvider(DatabaseProvider):
    """MySQL 数据库实现（SQLAlchemy + PyMySQL）。

    生产默认后端：
    - 连接池：pool_size / max_overflow / pool_recycle / pool_pre_ping；
    - 统一北京时间（UTC+8）：MySQL 系统时区默认 UTC，不设置时
      CURRENT_TIMESTAMP 默认值会比本地早 8 小时。
    """

    def __init__(
        self,
        database_url: str,
        pool_size: int = 5,
        max_overflow: int = 10,
        pool_recycle: int = 3600,
        echo: bool = False,
    ) -> None:
        if not database_url:
            raise ValueError("DATABASE_URL 配置不能为空，请在配置文件或环境变量中设置")
        if database_url.startswith("mysql://"):
            database_url = database_url.replace("mysql://", "mysql+pymysql://", 1)
        self._engine = create_engine(
            database_url,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_pre_ping=True,
            pool_recycle=pool_recycle,
            echo=echo,
            connect_args={"init_command": "SET time_zone = '+08:00'"},
        )
        self._session_factory = sessionmaker(
            bind=self._engine,
            autoflush=False,
            expire_on_commit=False,
        )
        logger.info(f"MySqlProvider initialized: {_mask_dsn(database_url)}")

    def get_engine(self) -> Engine:
        return self._engine

    def get_session_factory(self) -> sessionmaker[Session]:
        return self._session_factory

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def check_connection(self) -> bool:
        try:
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.warning(f"Database connection check failed: {e}")
            return False

    def close(self) -> None:
        self._engine.dispose()
        logger.info("MySQL connection closed")


# ============================================================
# SQLite 实现（回退后端）
# ============================================================
class SqliteProvider(DatabaseProvider):
    """SQLite 数据库实现（本地开发 / 单机部署回退后端）。

    - 无连接池语义（SQLite 单文件，create_engine 自动管理连接）；
    - check_same_thread=False：允许 FastAPI 线程池跨线程访问。
    """

    def __init__(self, database_url: str, echo: bool = False) -> None:
        if not database_url:
            raise ValueError("DATABASE_URL 配置不能为空，请在配置文件或环境变量中设置")
        # 相对路径 sqlite 锚定到服务根目录，避免随 CWD 漂移写入仓库根目录
        database_url = _anchor_sqlite_url(database_url)
        self._engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            echo=echo,
        )
        self._session_factory = sessionmaker(
            bind=self._engine,
            autoflush=False,
            expire_on_commit=False,
        )
        logger.info(f"SqliteProvider initialized: {_mask_dsn(database_url)}")

    def get_engine(self) -> Engine:
        return self._engine

    def get_session_factory(self) -> sessionmaker[Session]:
        return self._session_factory

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def check_connection(self) -> bool:
        try:
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.warning(f"Database connection check failed: {e}")
            return False

    def close(self) -> None:
        self._engine.dispose()
        logger.info("SQLite connection closed")


# ============================================================
# Provider 工厂
# ============================================================
def _build_provider(database_url: str) -> DatabaseProvider:
    """按 URL scheme 选择数据库后端实现。

    Args:
        database_url: SQLAlchemy 数据库 URL（mysql:// 或 sqlite:// 前缀）

    Returns:
        DatabaseProvider: 对应的数据库提供者实例

    Raises:
        ValueError: 不支持的 scheme
    """
    if database_url.startswith("mysql"):
        return MySqlProvider(database_url=database_url, echo=settings.DEBUG)
    if database_url.startswith("sqlite"):
        return SqliteProvider(database_url=database_url, echo=settings.DEBUG)
    scheme = database_url.split("://", 1)[0]
    raise ValueError(f"不支持的数据库 scheme: {scheme}（支持 mysql / sqlite）")


def get_database_provider() -> DatabaseProvider:
    """根据配置创建数据库提供者实例（每次调用新建，测试可覆盖）。"""
    return _build_provider(settings.DATABASE_URL)


# 模块级缓存实例（应用级单例）
_db_provider: DatabaseProvider | None = None


def get_cached_database_provider() -> DatabaseProvider:
    """获取缓存的数据库提供者（应用级单例，首次调用创建）。"""
    global _db_provider
    if _db_provider is None:
        _db_provider = get_database_provider()
    return _db_provider


# ============================================================
# 初始化与依赖入口（保持既有 API 兼容）
# ============================================================
def init_database() -> Engine:
    """初始化数据库，创建所有表。"""

    from qingchuan_rag.models.audit_log_entity import AuditLogEntity  # noqa: F401
    from qingchuan_rag.models.document_entity import DocumentEntity  # noqa: F401
    from qingchuan_rag.models.sync_task_entity import SyncTaskEntity  # noqa: F401

    engine = get_cached_database_provider().get_engine()
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created")


def get_db_session() -> Generator[Session]:
    """FastAPI 依赖：获取数据库会话（请求结束时自动提交 / 回滚 / 关闭）。

    Yields:
        Session: 数据库会话
    """
    session = get_cached_database_provider().get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Session:
    """非请求上下文获取会话（CLI 脚本 / 启动初始化用）。

    Returns:
        Session: 独立会话（调用方负责 close）
    """
    return get_cached_database_provider().get_session_factory()()


def _mask_dsn(url: str) -> str:
    """脱敏数据库 URL 的密码部分，用于日志输出。

    示例：mysql+pymysql://user:pass@host:3306/db → mysql+pymysql://user:***@host:3306/db
    """
    try:
        head, _, tail = url.partition("://")
        if "@" in tail:
            userinfo, _, host_part = tail.rpartition("@")
            username = userinfo.split(":", 1)[0]
            return f"{head}://{username}:***@{host_part}"
        return url
    except Exception:
        return "<invalid-dsn>"


__all__ = [
    "Base",
    "DatabaseProvider",
    "MySqlProvider",
    "SqliteProvider",
    "get_database_provider",
    "get_cached_database_provider",
    "init_database",
    "get_db_session",
    "get_session",
]
