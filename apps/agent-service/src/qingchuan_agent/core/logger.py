#!/usr/bin/env python3
"""
统一日志管理模块（晴川 x-QingChuan，对齐北辰 core/logger 写法）
基于 loguru 实现，支持：
    - JSON 结构化日志（生产） / 彩色控制台格式（开发）
    - 自动注入 request_id（middleware 的 logger.contextualize() 实现）
    - 文件始终输出 JSON，日志轮转与自动清理
    - 兜底：非请求上下文日志 request_id 为 "-"

Usage:
    from qingchuan_agent.core.logger import logger, setup_logging
    setup_logging()          # 应用入口处调用一次
    logger.info("...")
"""

from __future__ import annotations

import json as _json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger as _logger

if TYPE_CHECKING:
    from loguru import Logger, Record

from qingchuan_agent.constants import APP_NAME

_logger.remove()

_configured: bool = False
_DEFAULT_REQUEST_ID: str = "-"

# 彩色控制台格式（开发环境人可读）
_CONSOLE_FORMAT: str = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "<yellow>{extra[request_id]}</yellow> | "
    "<level>{message}</level>"
)


def _json_serializer(record: Record) -> str:
    """将 loguru 日志记录序列化为扁平 JSON 字符串。"""
    log_entry: dict[str, object] = {
        "timestamp": record["time"].isoformat(),
        "level": record["level"].name,
        "logger": record["name"],
        "function": record["function"],
        "line": record["line"],
        "message": record["message"],
        "request_id": record["extra"].get("request_id", _DEFAULT_REQUEST_ID),
    }
    if record["exception"] is not None:
        log_entry["exception"] = {
            "type": record["exception"].type.__name__ if record["exception"].type else "Exception",
            "value": str(record["exception"].value),
        }
    return _json.dumps(log_entry, ensure_ascii=False)


def _json_formatter(record: Record) -> str:
    record["extra"]["json_output"] = _json_serializer(record) + "\n"
    return "{extra[json_output]}"


def setup_logging(
    level: str | None = None,
    file_path: str | None = None,
    rotation: str | None = None,
    retention: str | None = None,
    log_format: str | None = None,
) -> None:
    """初始化日志配置，全局只能调用一次。控制台按 log_format 切换 json/console，文件始终 JSON。"""
    global _configured
    if _configured:
        return
    from qingchuan_agent.core.config import settings

    log_level: str = level or settings.logging.level
    log_file_path: str = file_path or settings.logging.file_path
    # 相对路径基于服务根目录（src 的上级目录）解析，
    # 保证任意 CWD 启动日志落位一致（对齐 rag-service）
    if not os.path.isabs(log_file_path):
        service_root = Path(__file__).parent.parent.parent.parent.resolve()
        log_file_path = str(service_root / log_file_path)
    log_rotation: str = rotation or settings.logging.rotation
    log_retention: str = retention or settings.logging.retention
    fmt: str = (log_format or settings.logging.format).lower()
    use_json_console: bool = fmt == "json"
    log_dir: str = os.path.dirname(log_file_path)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    _logger.remove()
    # 控制台输出
    if use_json_console:
        _logger.add(sink=sys.stderr, format=_json_formatter, level=log_level, enqueue=True)
    else:
        _logger.add(
            sink=sys.stderr,
            format=_CONSOLE_FORMAT,
            level=log_level,
            colorize=True,
            enqueue=True,
        )
    # 文件输出（始终 JSON）
    _logger.add(
        sink=log_file_path,
        format=_json_formatter,
        level=log_level,
        rotation=log_rotation,
        retention=log_retention,
        compression="zip",
        enqueue=True,
    )
    # 兜底：确保所有日志记录都有 request_id 字段
    _logger.configure(
        patcher=lambda record: record["extra"].setdefault("request_id", _DEFAULT_REQUEST_ID)
    )
    _configured = True


def get_logger() -> Logger:
    """获取全局日志实例。"""
    return _logger


def get_log_file_path() -> str:
    """获取日志文件路径。"""
    from qingchuan_agent.core.config import settings

    base_path: str = settings.logging.file_path
    if base_path:
        # 与 setup_logging 一致：相对路径基于服务根目录解析
        if not os.path.isabs(base_path):
            service_root = Path(__file__).parent.parent.parent.parent.resolve()
            base_path = str(service_root / base_path)
        dir_path: str = os.path.dirname(base_path)
        ext: str = os.path.splitext(base_path)[1] or ".log"
        return os.path.join(dir_path, f"{APP_NAME}-{{time:YYYYMMDDHH}}{ext}")
    # 兜底：未配置 LOG_FILE_PATH 时也落到服务根目录 logs/ 下，避免写入 CWD（如仓库根目录）
    service_root = Path(__file__).parent.parent.parent.parent.resolve()
    return str(service_root / f"logs/{APP_NAME}-{{time:YYYYMMDDHH}}.log")


logger = _logger

__all__ = ["get_log_file_path", "get_logger", "logger", "setup_logging"]
