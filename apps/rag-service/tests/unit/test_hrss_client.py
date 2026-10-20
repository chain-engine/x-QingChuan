#!/usr/bin/env python3
"""人社数据源接口层单元测试（infras/hrss.py 薄封装）。"""

import pytest

from qingchuan_rag.infras.hrss import SOURCE_HRSS, HRSSDataSourceClient


class TestMockMode:
    """mock 模式：不联网返回本地示例记录。"""

    @pytest.fixture
    def client(self) -> HRSSDataSourceClient:
        return HRSSDataSourceClient(mock=True, mock_count=3)

    def test_fetch_full(self, client: HRSSDataSourceClient) -> None:
        records = client.fetch_full(batch_size=10)
        # 3 参保人 + 2 政策（mock 政策固定 2 条，参保人按 mock_count）
        assert len(records) >= 4
        assert all("record_type" in r for r in records)

    def test_fetch_incremental(self, client: HRSSDataSourceClient) -> None:
        records = client.fetch_incremental(since=None, batch_size=10)
        assert len(records) >= 4

    def test_every_record_maps_to_text_and_metadata(self, client: HRSSDataSourceClient) -> None:
        for record in client.fetch_full():
            assert client._build_document_text(record).strip()  # noqa: SLF001
            metadata = client._build_document_metadata(record)  # noqa: SLF001
            assert metadata["source_type"] == SOURCE_HRSS
            assert metadata["record_id"]
            assert metadata["record_type"] in ("insured_person", "policy")

    def test_policy_metadata_has_category(self, client: HRSSDataSourceClient) -> None:
        policy = next(r for r in client.fetch_full() if r["record_type"] == "policy")
        assert client._build_document_metadata(policy)["category"]  # noqa: SLF001


class TestRealClient:
    """真实模式：走 infras/http.py 的 HTTP 能力（不实际发请求，只验证装配）。"""

    def test_auth_headers_token(self) -> None:
        assert HRSSDataSourceClient._build_auth_headers("tk-123") == {
            "Authorization": "Bearer tk-123"
        }
        assert HRSSDataSourceClient._build_auth_headers("") == {}

    def test_base_url_passed_to_http_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from qingchuan_rag.core.config import settings
        from qingchuan_rag.infras import hrss as hrss_module

        captured: dict[str, object] = {}

        def fake_provider(**kwargs: object) -> object:
            captured.update(kwargs)
            return object()

        monkeypatch.setattr(settings.sync, "data_source_mock", False)
        monkeypatch.setattr(settings.sync, "data_source_url", "https://hrss.example.com")
        monkeypatch.setattr(settings.sync, "data_source_timeout", 12.5)
        # hrss.py 以 from ...http import get_http_provider 引入，需在该模块命名空间替换
        monkeypatch.setattr(hrss_module, "get_http_provider", fake_provider)
        HRSSDataSourceClient(mock=False)
        assert captured["base_url"] == "https://hrss.example.com"
        assert captured["timeout"] == 12
