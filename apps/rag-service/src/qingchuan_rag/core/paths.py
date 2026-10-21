"""服务路径锚定工具：将相对路径统一解析到服务根目录（apps/rag-service）。

背景：文档存储 / BM25 / 向量库 / SQLite 等运行时路径默认写成 "./data/..."，
若直接传给底层（chromadb / milvus-lite / SQLAlchemy），会按进程 CWD 解析，
导致从仓库根目录启动服务时，把运行时数据写到仓库根目录 data/ 下。

本模块把相对路径锚定到服务根目录（apps/rag-service/data/...），
与 core/logger.py 的日志落位规则保持一致，保证任意 CWD 启动落位一致。
"""

from __future__ import annotations

import os
from pathlib import Path

# 服务根目录：apps/rag-service（本文件位于 src/qingchuan_rag/core/ 下，向上 4 级）
SERVICE_ROOT: Path = Path(__file__).resolve().parents[3]


def resolve_service_path(path: str | os.PathLike[str]) -> str:
    """相对路径基于服务根目录解析；绝对路径 / 远程地址（含://）原样返回。

    Examples:
        - "./data/chroma"          -> "<SERVICE_ROOT>/data/chroma"
        - "E:/abs/path"            -> 原样返回
        - "http://milvus:19530"    -> 原样返回（远程 Milvus）
    """
    value = os.fspath(path)
    if not value or os.path.isabs(value) or "://" in value:
        return value
    return str(SERVICE_ROOT / value)
