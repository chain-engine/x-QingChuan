#!/usr/bin/env python3
"""
Response Schema Module

统一响应格式定义。

响应信封以 qingchuan_common.http.response 为单一事实来源：
    - ResponseModel  = common ApiResponse（code / message / data / timestamp / request_id）
    - PageModel      = common Page（通用分页）
早期本模块的本地 ResponseModel（无 timestamp）、dict 版 success_response / error_response
与 ErrorResponse / ErrorDetail 均无业务使用点，已随统一信封收敛删除。
"""

from qingchuan_common.http.response import ApiResponse, Page

ResponseModel = ApiResponse
"""统一响应模型（common ApiResponse 别名，保持 rag 既有导入路径）。"""

PageModel = Page
"""分页响应模型（common Page 别名，保持 rag 既有导入路径）。"""

__all__ = ["PageModel", "ResponseModel"]
