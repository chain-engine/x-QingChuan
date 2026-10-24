"""领域 Schema（Pydantic 数据契约）。"""

from qingchuan_domain.schemas.rag import RAGQueryRequest, RAGQueryResponse, from_search_results
from qingchuan_domain.schemas.retrieval import RetrievalQuery, RetrievalResponse, RetrievedChunk
from qingchuan_domain.schemas.sync import SyncTaskResult, SyncTaskStatus, SyncTriggerRequest

__all__ = [
    "RAGQueryRequest",
    "RAGQueryResponse",
    "RetrievalQuery",
    "RetrievalResponse",
    "RetrievedChunk",
    "SyncTaskResult",
    "SyncTaskStatus",
    "SyncTriggerRequest",
    "from_search_results",
]
