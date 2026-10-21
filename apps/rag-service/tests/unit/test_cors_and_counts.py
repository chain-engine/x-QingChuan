"""CORS 中间件与检索统计的单元测试。

覆盖本轮修复：
- CORS：通配来源自动关闭 credentials（浏览器禁止"*"+凭证）；生产环境禁止通配来源（与 agent 对齐）；
- get_vector_count：多路候选 provider 求和（原实现只返回第一个）。
"""
from __future__ import annotations

import pytest
from starlette.applications import Starlette

from qingchuan_rag.core.config import settings
from qingchuan_rag.core.middleware import get_cors_origins, setup_cors_middleware


class TestCorsMiddleware:
    def test_cors_origins_parse(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "CORS_ALLOW_ORIGINS", "http://a.com, http://b.com")
        assert get_cors_origins() == ["http://a.com", "http://b.com"]

    def test_cors_origins_default_wildcard(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "CORS_ALLOW_ORIGINS", "*")
        assert get_cors_origins() == ["*"]

    def test_wildcard_origin_disables_credentials(self, monkeypatch) -> None:
        """开发环境默认 * + credentials=True → 自动降级 credentials=False"""
        monkeypatch.setattr(settings, "SERVER_ENVIRONMENT", "development")
        monkeypatch.setattr(settings.cors, "allow_credentials", True)
        monkeypatch.setattr(settings, "CORS_ENABLED", True)

        app = Starlette()
        setup_cors_middleware(app)

        cors_middlewares = [
            m for m in app.user_middleware if m.cls.__name__ == "CORSMiddleware"
        ]
        assert cors_middlewares, "应注册 CORSMiddleware"
        kwargs = cors_middlewares[0].kwargs
        assert "*" in kwargs["allow_origins"]
        assert kwargs["allow_credentials"] is False

    def test_explicit_origins_keep_credentials(self, monkeypatch) -> None:
        """显式来源列表时允许携带凭证"""
        monkeypatch.setattr(settings, "SERVER_ENVIRONMENT", "development")
        monkeypatch.setattr(settings.cors, "allow_credentials", True)
        monkeypatch.setattr(settings, "CORS_ALLOW_ORIGINS", "http://localhost:3000")
        monkeypatch.setattr(settings, "CORS_ENABLED", True)

        app = Starlette()
        setup_cors_middleware(app)

        cors_middlewares = [
            m for m in app.user_middleware if m.cls.__name__ == "CORSMiddleware"
        ]
        kwargs = cors_middlewares[0].kwargs
        assert kwargs["allow_origins"] == ["http://localhost:3000"]
        assert kwargs["allow_credentials"] is True

    def test_production_rejects_wildcard_origin(self, monkeypatch) -> None:
        """生产环境含 * 直接阻断启动（与 agent-service 校验对齐）"""
        monkeypatch.setattr(settings, "SERVER_ENVIRONMENT", "production")
        monkeypatch.setattr(settings, "CORS_ENABLED", True)

        app = Starlette()
        with pytest.raises(ValueError, match="不能为"):
            setup_cors_middleware(app)


class TestGetVectorCount:
    def test_sums_all_candidate_providers(self) -> None:
        """多路候选（vector + bm25）count 求和，而非只取第一个"""
        from qingchuan_rag.rag.retrieval import Retrieval

        retrieval = Retrieval()  # 空仓库构造（仅用于验证统计口径）

        class FakePipeline:
            def get_stats(self) -> dict:
                return {
                    "candidate_stats": {
                        "vector_retrieval": {"type": "vector", "count": 3},
                        "bm25_retrieval": {"type": "bm25", "count": 5},
                    }
                }

        retrieval._pipeline = FakePipeline()  # type: ignore[attr-defined]
        retrieval._initialized = True

        assert retrieval.get_vector_count() == 8

    def test_handles_missing_or_non_dict_stats(self) -> None:
        from qingchuan_rag.rag.retrieval import Retrieval

        retrieval = Retrieval()

        class FakePipeline:
            def get_stats(self) -> dict:
                return {
                    "candidate_stats": {
                        "vec": {"count": 2},
                        "bm25": {"initialized": False},  # 无 count
                        "broken": "not-a-dict",
                    }
                }

        retrieval._pipeline = FakePipeline()  # type: ignore[attr-defined]
        retrieval._initialized = True

        assert retrieval.get_vector_count() == 2

    def test_empty_candidates_returns_zero(self) -> None:
        from qingchuan_rag.rag.retrieval import Retrieval

        retrieval = Retrieval()

        class FakePipeline:
            def get_stats(self) -> dict:
                return {"candidate_stats": {}}

        retrieval._pipeline = FakePipeline()  # type: ignore[attr-defined]
        retrieval._initialized = True

        assert retrieval.get_vector_count() == 0
