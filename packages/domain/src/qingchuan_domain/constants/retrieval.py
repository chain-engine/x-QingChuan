"""共享领域协议层：检索相关默认常量（跨服务单一事实来源）。

HTTP / MCP 接入层默认参数（schemas/rag.py、mcp_server/tools.py）与本模块
对齐；rag-service 与 agent-service 共用同一套默认值，避免口径漂移。
"""

from __future__ import annotations

from typing import Final

DEFAULT_TOP_K: Final[int] = 5
DEFAULT_SIMILARITY_THRESHOLD: Final[float] = 0.7
DEFAULT_MMR_LAMBDA: Final[float] = 0.5
DEFAULT_TEMPERATURE: Final[float] = 0.7
DEFAULT_MAX_TOKENS: Final[int] = 2000

__all__ = [
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_MMR_LAMBDA",
    "DEFAULT_SIMILARITY_THRESHOLD",
    "DEFAULT_TEMPERATURE",
    "DEFAULT_TOP_K",
]
