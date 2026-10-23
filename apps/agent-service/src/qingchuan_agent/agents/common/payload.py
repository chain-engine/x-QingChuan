"""payload 字段提取工具（晴川 x-QingChuan，agents/common）。

任务 payload 由调用方按各 Agent 自定义结构传入；本模块收敛
"从 payload 稳妥取值"的公共逻辑（多字段回退 / 类型容错），
业务 Agent 无需重复处理脏输入。
"""

from __future__ import annotations

from typing import Any


def extract_query(
    payload: dict[str, Any],
    keys: tuple[str, ...] = ("query", "message", "question"),
) -> str:
    """按优先级取第一个非空文本字段作为查询文本（trim 后返回）。

    Args:
        payload: 任务入参
        keys: 候选字段名（按优先级排列）

    Returns:
        首个非空字符串；全部缺失返回空串（由调用方决定空值语义）。
    """
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def get_int(payload: dict[str, Any], key: str, default: int) -> int:
    """安全提取整型字段（容忍字符串数字），非法值回退默认。"""
    value = payload.get(key)
    if isinstance(value, bool):  # bool 是 int 子类，显式排除
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


__all__ = ["extract_query", "get_int"]
