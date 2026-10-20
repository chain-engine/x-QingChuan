"""晴川（x-QingChuan）共享领域包：实体、Schema、检索/同步协议、常量与端口。"""

from qingchuan_domain.entities import InsuredPerson
from qingchuan_domain.exceptions import (
    AppException,
    BusinessError,
    ConfigurationError,
    ConflictError,
    DatabaseError,
    DocumentError,
    EmbeddingError,
    ForbiddenError,
    GenerationError,
    NotFoundError,
    RateLimitError,
    RetrievalError,
    SyncError,
    SystemError,
    UnauthorizedError,
    ValidationError,
    VectorStoreError,
)
from qingchuan_domain.ports import HRSSDataSourcePort, RetrievalPort, SyncPort
from qingchuan_domain.schemas.retrieval import RetrievalQuery, RetrievalResponse, RetrievedChunk
from qingchuan_domain.schemas.sync import SyncTaskResult, SyncTaskStatus, SyncTriggerRequest

__all__ = [  # noqa: RUF022 - 按语义分组排序，保留可读性
    # 实体
    "InsuredPerson",
    # 检索协议
    "RetrievalQuery",
    "RetrievalResponse",
    "RetrievedChunk",
    "RetrievalPort",
    # 同步协议
    "SyncTriggerRequest",
    "SyncTaskStatus",
    "SyncTaskResult",
    "HRSSDataSourcePort",
    "SyncPort",
    # 异常
    "AppException",
    "BusinessError",
    "SystemError",
    "NotFoundError",
    "ValidationError",
    "UnauthorizedError",
    "ForbiddenError",
    "ConflictError",
    "RateLimitError",
    "DocumentError",
    "SyncError",
    "EmbeddingError",
    "VectorStoreError",
    "RetrievalError",
    "GenerationError",
    "DatabaseError",
    "ConfigurationError",
]

__version__ = "0.2.0"
