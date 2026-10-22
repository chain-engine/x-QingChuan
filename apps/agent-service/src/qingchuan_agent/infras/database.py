#!/usr/bin/env python3
"""数据库基础设施（晴川 x-QingChuan，对齐北辰 infras/database）。

提供数据库连接池管理和会话工厂，确保数据库连接的高效复用和生命周期管理：
    - 基于 SQLAlchemy 2.0 的同步支持
    - MySQL 连接池管理与配置（统一北京时间 UTC+8）
    - 上下文管理器确保会话自动关闭

Usage:
    from qingchuan_agent.infras.database import get_cached_database_provider, Base
    provider = get_cached_database_provider()
    with provider.session() as session:
        result = session.execute(select(User))
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from qingchuan_agent.core.config import settings
from qingchuan_agent.core.logger import logger
from qingchuan_agent.utils.helpers import mask_url_credentials


class Base(DeclarativeBase):
    """ORM 声明式基类（SQLAlchemy 2.0 风格，mypy 可识别）。"""


# ============================================================
# 抽象基类
# ============================================================


class DatabaseProvider(ABC):
    """数据库提供者抽象接口。

    所有数据库后端必须实现此接口。业务层仅依赖此抽象，
    切换数据库实现只需修改配置，无需改动任何业务代码。
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
        """获取数据库会话的上下文管理器。"""

    @abstractmethod
    def check_connection(self) -> bool:
        """检测数据库连接是否可用。"""

    @abstractmethod
    def close(self) -> None:
        """关闭数据库连接，释放资源。"""


# ============================================================
# MySQL (SQLAlchemy) 实现
# ============================================================


class MySqlProvider(DatabaseProvider):
    """MySQL 数据库实现（基于 SQLAlchemy）。"""

    def __init__(
        self,
        database_url: str,
        pool_size: int = 5,
        max_overflow: int = 10,
        pool_timeout: int = 30,
        pool_recycle: int = 3600,
        echo: bool = False,
    ) -> None:
        if not database_url:
            raise ValueError("DATABASE_URL 配置不能为空，请在配置文件或环境变量中设置")
        if database_url.startswith("mysql://"):
            database_url = database_url.replace("mysql://", "mysql+pymysql://")
        self._engine = create_engine(
            database_url,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            pool_pre_ping=True,
            pool_recycle=pool_recycle,
            echo=echo,
            # 统一存储北京时间（UTC+8）：MySQL 系统时区为 UTC，
            # 不设置时区时 CURRENT_TIMESTAMP 默认值会落 UTC，比本地早 8 小时。
            connect_args={"init_command": "SET time_zone = '+08:00'"},
        )
        self._session_factory = sessionmaker(
            bind=self._engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
        logger.info(f"MySqlProvider initialized: {mask_url_credentials(database_url)}")

    def get_engine(self) -> Engine:
        return self._engine

    def get_session_factory(self) -> sessionmaker[Session]:
        return self._session_factory

    @contextmanager
    def session(self) -> Iterator[Session]:
        """获取数据库会话的上下文管理器。"""
        session: Session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"MySQL operation failed, rolled back: {e}")
            raise
        finally:
            session.close()

    def check_connection(self) -> bool:
        """检测数据库连接是否可用。"""
        try:
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.warning(f"Database connection check failed: {e}")
            return False

    def close(self) -> None:
        if self._engine:
            self._engine.dispose()
            logger.info("MySQL connection closed")


# ============================================================
# 工厂函数
# ============================================================


def get_database_provider() -> DatabaseProvider:
    """根据配置创建数据库提供者实例。"""
    return MySqlProvider(
        database_url=settings.database.url,
        pool_size=settings.database.pool_size,
        max_overflow=settings.database.max_overflow,
        pool_timeout=settings.database.pool_timeout,
        pool_recycle=settings.database.pool_recycle,
        echo=settings.database.echo,
    )


# 模块级缓存实例
_db_provider: DatabaseProvider | None = None


def get_cached_database_provider() -> DatabaseProvider:
    """获取缓存的数据库提供者（应用级别单例）。"""
    global _db_provider
    if _db_provider is None:
        _db_provider = get_database_provider()
    return _db_provider


# ============================================================
# 初始化
# ============================================================


def _sync_missing_columns(engine: Engine) -> None:
    """补齐已存在表上模型新增的列（与建表逻辑互补：create_all 只建表、不补列）。

    模型演进新增列后，旧表通过 `ALTER TABLE ... ADD COLUMN` 自动对齐，
    避免 SELECT 引用不存在的列导致 (1054, "Unknown column ...") 运行时错误。
    无法安全编译的列（如客户端默认值）跳过并告警，不阻断启动。
    """
    added: list[str] = []
    inspector = inspect(engine)
    for table_name, table in Base.metadata.tables.items():
        if not inspector.has_table(table_name):
            continue  # 缺失表交由 init_database 的建表逻辑创建
        existing = {col["name"] for col in inspector.get_columns(table_name)}
        for column in table.columns:
            if column.name in existing:
                continue
            try:
                type_sql = column.type.compile(engine.dialect)
                default_sql = ""
                if column.server_default is not None:
                    raw = column.server_default.arg
                    if isinstance(raw, str):
                        default_sql = f" DEFAULT {raw}"
                    elif hasattr(raw, "text"):
                        default_sql = f" DEFAULT {raw.text}"
                nullable_sql = "NULL" if column.nullable else "NOT NULL"
                ddl = (
                    f"ALTER TABLE {table_name} ADD COLUMN "
                    f"{column.name} {type_sql} {nullable_sql}{default_sql}"
                )
                with engine.begin() as conn:
                    conn.execute(text(ddl))
                added.append(f"{table_name}.{column.name}")
                logger.info(f"Schema sync: added missing column {table_name}.{column.name}")
            except Exception:
                logger.warning(
                    f"Schema sync: skip column {table_name}.{column.name} "
                    f"(cannot compile ALTER, manual migration may be required)",
                    exc_info=True,
                )
    if added:
        logger.info(f"Schema sync: added {len(added)} missing column(s): {', '.join(added)}")


def init_database() -> None:
    """初始化 MySQL 数据库：检测缺失的表并创建（幂等，可重复调用），并对已存在表补齐模型新增列。

    与 `Base.metadata.create_all()` 的差异：
        create_all 会对每张表执行 DESCRIBE 探测后按需创建（行为等价幂等），
        但本函数先通过 inspector 一次拿到全部现有表名，只对缺失表执行 DDL，
        表已齐备时直接跳过，避免启动期逐表探测与日志噪音。
    """
    from qingchuan_agent.models import entities  # noqa: F401

    engine = get_cached_database_provider().get_engine()
    inspector = inspect(engine)
    existing = set(inspector.get_table_names())
    missing = [name for name in Base.metadata.tables if name not in existing]
    if missing:
        Base.metadata.create_all(
            bind=engine, tables=[Base.metadata.tables[name] for name in missing]
        )
        logger.info(f"MySQL 建表完成（新增：{sorted(missing)}）")
    else:
        logger.info(f"MySQL 表已齐备（{sorted(existing)}），跳过建表")
    _sync_missing_columns(engine)


__all__ = [
    "Base",
    "DatabaseProvider",
    "MySqlProvider",
    "get_cached_database_provider",
    "get_database_provider",
    "init_database",
]
