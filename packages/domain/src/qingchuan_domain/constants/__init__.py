"""共享领域协议层：领域常量（跨服务单一事实来源）。"""

from qingchuan_domain.constants.retrieval import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_MMR_LAMBDA,
    DEFAULT_SIMILARITY_THRESHOLD,
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_K,
)

__all__ = [
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_MMR_LAMBDA",
    "DEFAULT_SIMILARITY_THRESHOLD",
    "DEFAULT_TEMPERATURE",
    "DEFAULT_TOP_K",
]
