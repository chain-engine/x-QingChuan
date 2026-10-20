"""领域 Schema（Pydantic 数据契约）。"""

from qingchuan_domain.schemas.retrieval import RetrievalQuery, RetrievalResponse, RetrievedChunk
from qingchuan_domain.schemas.sync import SyncTaskResult, SyncTaskStatus, SyncTriggerRequest

__all__ = [
    "RetrievalQuery",
    "RetrievalResponse",
    "RetrievedChunk",
    "SyncTaskResult",
    "SyncTaskStatus",
    "SyncTriggerRequest",
]
