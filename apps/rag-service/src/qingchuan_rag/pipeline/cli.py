"""离线索引管道 CLI：人社数据同步 / 统计 / 存储迁移。

命令：
  sync  [--full] [--force]   执行一轮人社数据同步（默认增量）
  stats                      查看索引与最近同步统计
  migrate-documents [--source-dir DIR] [--dry-run]
                             旧版 JSON 文档存储 → documents 表 + 对象存储（幂等）

与 HTTP 触发接口（POST /api/v1/sync/trigger）共用 SyncService，
适用于部署脚本 / cron / 手动运维。
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence


def _parse_dt(value):
    """把旧 JSON 里的 ISO 时间字符串解析为 datetime（失败返回 None）。"""
    from datetime import datetime

    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


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
    doc_repo = DocumentRepository()
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


def _run_migrate_documents(source_dir: str | None, dry_run: bool) -> int:
    """旧版 JSON 文档存储 → documents 表 + 对象存储（幂等：已存在 document_id 跳过）。

    旧实现（JSONDocumentStore）每文档一个 {document_id}.json，仅存元数据不含原文；
    迁移将元数据入库 documents 表，并以原 JSON 记录作为内容对象写入存储层，
    保证内容层也完整可追溯。完成后旧目录建议人工归档 / 删除。
    """
    from pathlib import Path

    from qingchuan_rag.core.paths import resolve_service_path
    from qingchuan_rag.infras.database import init_database
    from qingchuan_rag.repositories.document_repository import DocumentRepository

    init_database()
    repo = DocumentRepository()
    repo.initialize()

    src = Path(resolve_service_path(source_dir or "./data/documents"))
    if not src.is_dir():
        print(f"旧 JSON 文档目录不存在: {src}")
        return 1

    files = sorted(src.glob("*.json"))
    if not files:
        print(f"旧 JSON 文档目录为空（无需迁移）: {src}")
        return 0

    migrated = skipped = failed = 0
    print(f"迁移源目录: {src}（共 {len(files)} 个 JSON 文件，dry_run={dry_run}）")
    for path in files:
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            document_id = data.get("document_id")
            if not document_id:
                failed += 1
                print(f"  [ERR] {path.name}: 缺少 document_id")
                continue
            if repo.exists(document_id):
                skipped += 1
                print(f"  [SKIP] {document_id} 已存在")
                continue

            # 内容对象：旧实现未存原文，以原 JSON 记录作为内容对象保留历史
            content_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
            content_key = f"documents/{document_id}.json"

            if dry_run:
                migrated += 1
                print(f"  [DRY] {document_id} {data.get('file_name', '')} -> {content_key}")
                continue

            repo.storage.upload_file(content_bytes, content_key, content_type="application/json")
            payload: dict = {
                "document_id": document_id,
                "file_name": data.get("file_name", ""),
                "file_type": data.get("file_type", "txt"),
                "file_size": int(data.get("file_size", 0) or 0),
                "status": data.get("status", "pending"),
                "chunk_count": int(data.get("chunk_count", 0) or 0),
                "content_key": content_key,
                "storage_backend": repo.storage.storage_type,
                "metadata": data.get("metadata") or {},
            }
            created_at = _parse_dt(data.get("created_at"))
            updated_at = _parse_dt(data.get("updated_at"))
            if created_at is not None:
                payload["created_at"] = created_at.isoformat()
            if updated_at is not None:
                payload["updated_at"] = updated_at.isoformat()
            repo.save(payload)
            migrated += 1
            print(f"  [OK ] {document_id} {data.get('file_name', '')} -> {content_key}")
        except Exception as e:  # noqa: BLE001 - 单文件失败不中断整批
            failed += 1
            print(f"  [ERR] {path.name}: {e}")

    print(f"迁移完成：迁移 {migrated}，跳过 {skipped}，失败 {failed}")
    return 0 if failed == 0 else 1


def main(argv: Sequence[str] | None = None) -> int:
    """CLI 入口。"""
    parser = argparse.ArgumentParser(prog="qingchuan-pipeline", description="晴川离线索引管道")
    subparsers = parser.add_subparsers(dest="command", required=True)

    sync_parser = subparsers.add_parser("sync", help="执行一轮人社数据同步")
    sync_parser.add_argument("--full", action="store_true", help="全量同步（默认增量）")
    sync_parser.add_argument("--force", action="store_true", help="忽略已同步标记强制重跑")

    subparsers.add_parser("stats", help="查看索引与最近同步统计")

    migrate_parser = subparsers.add_parser(
        "migrate-documents",
        help="旧版 JSON 文档存储 → documents 表 + 对象存储（幂等）",
    )
    migrate_parser.add_argument(
        "--source-dir",
        default=None,
        help="旧 JSON 文档目录（默认 ./data/documents，相对路径锚定服务根）",
    )
    migrate_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅预览迁移结果，不写入数据库与存储",
    )

    args = parser.parse_args(argv)

    if args.command == "sync":
        return _run_sync(full=args.full, force=args.force)
    if args.command == "migrate-documents":
        return _run_migrate_documents(source_dir=args.source_dir, dry_run=args.dry_run)
    return _run_stats()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
