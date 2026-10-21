#!/usr/bin/env python3
"""枚举基类族（re-export 共享领域包 qingchuan_domain.constants.base）。

基类实现与 (mark, desc) 二元组约定的单一事实来源在 packages/domain，
本模块仅做转发，保证 agent 内部既有导入路径不变。
"""

from qingchuan_domain.constants.base import BaseEnum, FloatBaseEnum, IntBaseEnum, StrBaseEnum

__all__ = ["BaseEnum", "FloatBaseEnum", "IntBaseEnum", "StrBaseEnum"]
