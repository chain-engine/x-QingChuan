#!/usr/bin/env python3
"""
HTTP 响应工具

提供统一的 JSONResponse 构造函数，避免各路由模块重复样板代码。

Functions:
    success_response: 构造统一成功响应
    error_response: 构造统一错误响应

实现以 qingchuan_common.http.response 为单一事实来源（统一信封
ApiResponse：code / message / data / timestamp / request_id），
本模块保留同名薄导出以维持 rag 既有导入路径。
"""

from qingchuan_common.http.response import error_response, success_response

__all__ = ["success_response", "error_response"]
