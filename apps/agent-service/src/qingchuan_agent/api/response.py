#!/usr/bin/env python3
"""API 响应工具（晴川 x-QingChuan）。

提供统一的 JSONResponse 构造函数，避免各路由模块重复样板代码：
    success_response: 构造统一成功响应
    error_response: 构造统一错误响应

实现以 qingchuan_common.http.response 为单一事实来源（统一信封
ApiResponse：code / message / data / timestamp / request_id），
本模块保留同名薄导出以维持 agent 既有导入路径。
"""

from __future__ import annotations

from qingchuan_common.http.response import error_response, success_response

__all__ = ["error_response", "success_response"]
