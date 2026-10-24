#!/usr/bin/env python3
"""统一响应与分页 Schema（晴川 x-QingChuan）。

统一响应信封以 qingchuan_common.http.response 为单一事实来源
（ApiResponse：code / message / data / timestamp / request_id；Page 通用分页），
本模块保留 re-export 以维持 agent 既有导入路径。
"""

from __future__ import annotations

from qingchuan_common.http.response import ApiResponse, Page

__all__ = ["ApiResponse", "Page"]
