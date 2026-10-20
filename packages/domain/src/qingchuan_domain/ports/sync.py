"""共享领域协议层：人社数据同步端口（实现侧不可侵入领域）。

同步编排（SyncService）只依赖 HRSSDataSourcePort 拉取人社数据、
依赖 SyncPort 完成"数据 → 向量库"落库，不感知具体数据源与向量实现。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from qingchuan_domain.schemas.sync import SyncTaskResult


@runtime_checkable
class HRSSDataSourcePort(Protocol):
    """人社数据源端口：拉取参保人 / 政策等离线数据。"""

    def fetch_incremental(
        self,
        since: datetime | None,
        batch_size: int,
    ) -> list[dict[str, Any]]:
        """增量拉取：返回自 since 以来变更的数据记录（原始字段）。

        TODO: 由 qingchuan_rag/sync/hrss_client.py 实现，接入人社 API 后
        落实分页 / 游标 / 认证 / 字段映射。
        """
        ...

    def fetch_full(self, batch_size: int) -> list[dict[str, Any]]:
        """全量拉取：返回全部数据记录（原始字段）。"""
        ...


@runtime_checkable
class SyncPort(Protocol):
    """人社 → 向量库同步端口。"""

    def sync_once(self, full: bool = False, force: bool = False) -> SyncTaskResult:
        """执行一次同步（拉取 → 清洗 → 分块 → 向量化 → 入库）。"""
        ...


__all__ = ["HRSSDataSourcePort", "SyncPort"]
