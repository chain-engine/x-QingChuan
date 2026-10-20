#!/usr/bin/env python3
"""全局常量（晴川 x-QingChuan，对齐北辰 constants/constants 写法）。

集中定义应用信息、API 路由等全局常量。禁止在业务代码中硬编码这些值。
按业务类别分组，以横线注释区分。
（枚举定义见 enums.py，枚举基类族见 base.py）
"""

from typing import Final

# ── 应用信息 ──────────────────────────────────────────
APP_ID: str = "x-QingChuan"
APP_NAME: str = "晴川（QingChuan）"
APP_DESCRIPTION: str = "晴川（QingChuan）：一个基于人社平台的多 Agent 编排和知识库赋能平台"
APP_VERSION: str = "0.1.0"

# ── API 路由 ──────────────────────────────────────────
# 具体版本号（/v1）已并入基础前缀；后续 Agent 对外 API 层路由在此统一引用
API_PREFIX: Final[str] = "/api/v1"
