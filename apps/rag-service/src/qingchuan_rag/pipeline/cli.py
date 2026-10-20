"""离线索引管道 CLI：人社数据同步 / 统计。

命令：
  sync  [--full] [--force]   执行一轮人社数据同步（默认增量）
  stats                      查看索引与最近同步统计

与 HTTP 触发接口（POST /api/v1/sync/trigger）共用 SyncService，
适用于部署脚本 / cron / 手动运维。
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence


def _build_sync_service():
    """独立进程装配（与 main.py lifespan 对齐，不启动 HTTP/MCP）。"""
    from qingchuan_rag.core.config import settings
    from qingchuan_rag.infras.database import init_database
    from qingchuan_rag.repositories.bm25_repository import BM25Repository
    from qingchuan_rag.repositories.document_repository import DocumentRepository
    from qingchuan_rag.repositories.vector_repository import VectorRepository
    from qingchuan_rag.services.audit_service import AuditService
    from qingchuan_rag.services.document_service import DocumentService
    from qingchuan_rag.services.sync_service import SyncService

    init_database()
    audit_service = AuditService()
    doc_repo = DocumentRepository(storage_path="./data/documents")
    bm25_repo = BM25Repository(
        persist_directory="./data/bm25",
        index_name="documents",
    )
    vector_repo = VectorRepository(
        persist_directory=settings.VECTOR_STORE_PERSIST_DIR,
        collection_name=settings.VECTOR_STORE_COLLECTION_NAME,
        distance_type=settings.VECTOR_STORE_DISTANCE,
    )
    document_service = DocumentService(
        vector_repo=vector_repo,
        doc_repo=doc_repo,
        bm25_repo=bm25_repo,
        chunk_size=settings.TEXT_SPLITTER_CHUNK_SIZE,
        chunk_overlap=settings.TEXT_SPLITTER_CHUNK_OVERLAP,
        chunking_provider=settings.TEXT_SPLITTER_PROVIDER,
        chunking_strategy=settings.TEXT_SPLITTER_STRATEGY,
        audit_service=audit_service,
    )
    sync_service = SyncService(
        document_service=document_service,
        audit_service=audit_service,
    )
    document_service.initialize()
    sync_service.initialize()
    return sync_service


def _run_sync(full: bool, force: bool) -> int:
    """执行一轮人社数据同步。"""
    from qingchuan_rag.core.logger import logger

    sync_service = _build_sync_service()
    result = sync_service.sync_once(full=full, force=force, channel="manual")
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
    logger.info(f"CLI 同步结束：task_id={result.task_id} status={result.status}")
    return 0 if result.status == "success" else 1


def _run_stats() -> int:
    """查看索引与最近同步统计。"""
    sync_service = _build_sync_service()
    print(json.dumps(sync_service.get_stats(), ensure_ascii=False, indent=2, default=str))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """CLI 入口。"""
    parser = argparse.ArgumentParser(prog="qingchuan-pipeline", description="晴川离线索引管道")
    subparsers = parser.add_subparsers(dest="command", required=True)

    sync_parser = subparsers.add_parser("sync", help="执行一轮人社数据同步")
    sync_parser.add_argument("--full", action="store_true", help="全量同步（默认增量）")
    sync_parser.add_argument("--force", action="store_true", help="忽略已同步标记强制重跑")

    subparsers.add_parser("stats", help="查看索引与最近同步统计")

    args = parser.parse_args(argv)

    if args.command == "sync":
        return _run_sync(full=args.full, force=args.force)
    return _run_stats()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
