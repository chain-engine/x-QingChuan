#!/usr/bin/env python3
"""人社（社保）平台服务接口层。

薄封装：仅做"调用社保平台服务 + 把记录映射为可索引文档"两件事，
HTTP 请求能力复用 infras/http.py（RequestsHttpProvider）。

接入真实接口时只需调整三处（均在本文件）：
    1. 端点路径（PATH_* 常量）与认证方式（token 或自定义签名）；
    2. 返回字段名（_parse_items / 记录字段提取）；
    3. 文本 / 元数据映射（_build_document_text / _build_document_metadata）。

未配置真实地址时（HRSS_MOCK=true，默认）返回本地示例数据，
保证同步链路（触发 → 索引 → 检索）可端到端调试。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from qingchuan_rag.core.config import settings
from qingchuan_rag.core.logger import logger
from qingchuan_rag.infras.http import HttpProvider, get_http_provider

SOURCE_HRSS: str = "hrss"
TYPE_INSURED: str = "insured_person"
TYPE_POLICY: str = "policy"

# ── 端点路径（真实接口文档到位后整体替换）────────────────────────────
PATH_INSURED_PERSONS: str = "/api/hrss/insured-persons"  # 参保人列表
PATH_POLICIES: str = "/api/hrss/policies"  # 政策条文列表


class HRSSDataSourceClient:
    """社保平台数据源客户端（真实 HTTP 或本地 Mock，由 HRSS_MOCK 决定）。"""

    def __init__(
        self,
        base_url: str = "",
        token: str = "",
        batch_size: int = 100,
        mock: bool | None = None,
        mock_count: int | None = None,
    ) -> None:
        self._batch_size = batch_size or settings.SYNC_BATCH_SIZE
        self._use_mock = settings.HRSS_MOCK if mock is None else mock
        self._mock_count = max(1, min(mock_count or settings.HRSS_MOCK_COUNT, 100))
        self._http: HttpProvider | None = None
        if not self._use_mock:
            url = (base_url or settings.HRSS_API_URL).rstrip("/")
            self._http = get_http_provider(
                base_url=url,
                timeout=int(settings.HRSS_API_TIMEOUT),
                retries=3,
            )
            self._headers = self._build_auth_headers(token or settings.HRSS_API_TOKEN)
            if not url:
                logger.warning("HRSS_API_URL 未配置，人社数据源将以空结果运行")
        else:
            logger.warning(
                f"HRSS_MOCK=true：人社数据源使用本地示例数据（{self._mock_count} 条），"
                "接入真实接口后请关闭 mock 并配置 HRSS_API_URL"
            )

    # ── 领域端口（SyncService 消费）─────────────────────────────────
    def fetch_full(self, batch_size: int | None = None) -> list[dict[str, Any]]:
        """全量拉取数据记录（参保人 + 政策）。"""
        size = batch_size or self._batch_size
        logger.info(f"人社数据全量拉取：batch_size={size}")
        return self._fetch_all(size, updated_after=None)

    def fetch_incremental(
        self,
        since: datetime | None,
        batch_size: int | None = None,
    ) -> list[dict[str, Any]]:
        """增量拉取自 since 以来变更的数据记录。

        TODO(真实接入)：人社接口若支持更新时间过滤则传 updated_after；
        否则全量拉取后在 SyncService 侧以 sync_tasks.extra 持久化游标本地去重。
        """
        size = batch_size or self._batch_size
        since_str = since.astimezone(UTC).isoformat(timespec="seconds") if since else None
        logger.info(f"人社数据增量拉取：since={since_str} batch_size={size}")
        return self._fetch_all(size, updated_after=since_str)

    # ── 记录 → 文档映射（SyncService 复用）──────────────────────────
    def _build_document_text(self, record: dict[str, Any]) -> str:
        """人社记录 → 可检索文本。"""
        if record.get("record_type") == TYPE_POLICY:
            return "\n".join(filter(None, [record.get("title"), record.get("content")]))
        parts = [
            f"参保人：{record.get('name') or ''}",
            f"参保类型：{record.get('insured_type') or ''}",
            f"参保状态：{record.get('insured_status') or ''}",
            f"参保单位：{record.get('unit_name') or ''}",
        ]
        return "；".join(filter(None, parts))

    def _build_document_metadata(self, record: dict[str, Any]) -> dict[str, Any]:
        """人社记录 → 文档元数据（source_type/record_id/record_type 固定，业务可追加）。"""
        metadata: dict[str, Any] = {
            "source_type": SOURCE_HRSS,
            "record_id": record.get("id"),
            "record_type": record.get("record_type", TYPE_INSURED),
            "updated_at": record.get("updated_at"),
        }
        if record.get("record_type") == TYPE_POLICY and record.get("category"):
            metadata["category"] = record["category"]
        return metadata

    # ── 内部实现 ───────────────────────────────────────────────────
    def _fetch_all(self, size: int, updated_after: str | None) -> list[dict[str, Any]]:
        """拉取参保人 + 政策两类数据，归一为统一记录 dict（追加 record_type）。"""
        if self._use_mock:
            return self._mock_records()
        records: list[dict[str, Any]] = []
        for path, record_type in (
            (PATH_INSURED_PERSONS, TYPE_INSURED),
            (PATH_POLICIES, TYPE_POLICY),
        ):
            items = self._get_items(path, size, updated_after)
            for item in items:
                item["record_type"] = record_type
                records.append(item)
        # TODO(真实接入)：按分页字段循环拉满剩余页，直至拉完或触达上限
        logger.info(f"人社拉取汇总：共 {len(records)} 条记录")
        return records

    def _get_items(self, path: str, size: int, updated_after: str | None) -> list[dict[str, Any]]:
        """请求单页数据并提取记录列表（兼容 list / {data:[...]} / {data:{list:[...]}}）。"""
        assert self._http is not None
        params: dict[str, Any] = {"page": 1, "page_size": size}
        if updated_after:
            params["updated_after"] = updated_after
        payload = self._http.get(path, params=params, headers=self._headers)
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            data = payload.get("data", payload)
            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict)]
            if isinstance(data, dict):
                for key in ("list", "items", "records", "rows"):
                    value = data.get(key)
                    if isinstance(value, list):
                        return [item for item in value if isinstance(item, dict)]
        return []

    def _mock_records(self) -> list[dict[str, Any]]:
        """本地示例数据（内容带 [MOCK] 标记，便于检索结果识别）。"""
        now = datetime.now(UTC).isoformat(timespec="seconds")
        policies = [
            {
                "id": f"mock-policy-{i:03d}",
                "title": f"[MOCK] {t}",
                "content": f"[MOCK 示例数据，仅用于本地调试] {c}",
                "category": cat,
                "updated_at": now,
            }
            for i, (t, c, cat) in enumerate(
                (
                    (
                        "灵活就业人员参加企业职工基本养老保险办法",
                        "灵活就业人员可以个人身份参加企业职工基本养老保险，缴费基数可在规定范围内自主选择。",
                        "养老保险",
                    ),
                    (
                        "城乡居民基本医疗保险门诊统筹实施细则",
                        "参保居民在定点基层医疗机构发生的符合规定的普通门诊医疗费用，按比例由统筹基金支付。",
                        "医疗保险",
                    ),
                ),
                start=1,
            )
        ][: self._mock_count]
        insureds = [
            {
                "id": f"mock-insured-{i:03d}",
                "name": f"示例参保人{i}",
                "gender": "男" if i % 2 else "女",
                "insured_type": "城镇职工",
                "insured_status": "正常",
                "unit_name": "示例市某制造有限公司",
                "updated_at": now,
            }
            for i in range(1, self._mock_count + 1)
        ]
        return [{**p, "record_type": TYPE_POLICY} for p in policies] + [
            {**i, "record_type": TYPE_INSURED} for i in insureds
        ]

    @staticmethod
    def _build_auth_headers(token: str) -> dict[str, str]:
        """认证头：token → Bearer。

        TODO(真实接入)：若平台要求 appKey/appSecret 签名或 basic，在此扩展。
        """
        if token:
            return {"Authorization": f"Bearer {token}"}
        return {}


__all__ = ["HRSSDataSourceClient", "SOURCE_HRSS"]
