#!/usr/bin/env python3
"""通用工具函数（无状态、纯函数，对齐北辰 utils/helpers）。

集中存放未分类或不便分类的工具函数：路径解析、IP 提取、敏感信息脱敏等。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# ============================================================
# 路径解析
# ============================================================


def find_project_root() -> Path:
    """向上查找项目根目录。

    从当前文件所在位置向上逐级查找，直到找到包含 `pyproject.toml` 的目录
    （即 agent-service/ 目录），用于定位配置、日志等相对资源。

    Returns:
        Path: 项目根目录（apps/agent-service/）
    """
    current: Path = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    return current


# ============================================================
# 网络 / 请求
# ============================================================


def get_client_ip(request: Any) -> str:
    """提取客户端真实 IP。

    优先信任反向代理写入的 X-Forwarded-For / X-Real-IP，回退到直连地址。

    Args:
        request: Starlette / FastAPI Request 对象

    Returns:
        str: 客户端 IP
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    if hasattr(request, "client") and request.client:
        return request.client.host or "-"
    return "-"


# ============================================================
# 脱敏
# ============================================================

_SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "token",
        "api_key",
        "apikey",
        "access_key",
        "secret_key",
        "authorization",
        "cookie",
        "private_key",
    }
)


def mask_sensitive(data: Any, keys: list[str] | None = None) -> Any:
    """递归脱敏：将敏感 key 对应的值替换为掩码。

    用于请求日志、异常上下文等场景，避免泄露密钥与凭证。

    Args:
        data: 任意结构（dict / list / 标量）
        keys: 额外需要脱敏的 key 集合（默认使用内置敏感词表）

    Returns:
        脱敏后的深拷贝数据
    """
    sensitive_keys = _SENSITIVE_KEYS.union(set(keys or []))

    def _mask(value: Any) -> Any:
        if isinstance(value, dict):
            result: dict[str, Any] = {}
            for k, v in value.items():
                result[str(k)] = _mask(v) if str(k).lower() not in sensitive_keys else "***"
            return result
        if isinstance(value, list):
            return [_mask(item) for item in value]
        return value

    return _mask(data)


def mask_url_credentials(url: str) -> str:
    """脱敏 URL 中的账号密码（如数据库连接串）。

    例：mysql+pymysql://root:123456@host/db → mysql+pymysql://root:***@host/db

    Args:
        url: 原始连接串

    Returns:
        脱敏后的连接串（未匹配到凭据时原样返回）
    """
    if not url:
        return url
    return re.sub(r"(://[^:/@]+):([^@/]+)@", r"\1:***@", url)


__all__ = ["find_project_root", "get_client_ip", "mask_sensitive", "mask_url_credentials"]
