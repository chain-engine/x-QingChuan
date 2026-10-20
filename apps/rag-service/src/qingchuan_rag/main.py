#!/usr/bin/env python3
"""
晴川（QingChuan）应用（FastAPI）入口

一个支持 HTTP 与 MCP 双挂载的 RAG（检索增强生成）一体化服务：
以人社系统离线数据为知识源（触发接口 + 内置周期调度同步到向量库），
对外提供文档管理、检索问答与同步触发能力。

启动方式（命令行入口见 qingchuan_rag/cli.py）：
    cd apps/rag-service
    uv run qingchuan-rag-api           # 等价于 uv run python -m qingchuan_rag.cli
    uv run uvicorn qingchuan_rag.main:app --reload --host 0.0.0.0 --port 8010
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError

from qingchuan_rag.constants import HttpStatus
from qingchuan_rag.core.config import settings
from qingchuan_rag.core.exceptions import AppException
from qingchuan_rag.core.logger import logger, setup_logging
from qingchuan_rag.core.middleware import setup_middleware
from qingchuan_rag.http_server.response import error_response, success_response
from qingchuan_rag.http_server.router import api_router
from qingchuan_rag.infras.database import init_database
from qingchuan_rag.mcp_server.server import bind_rag_service, mcp_server
from qingchuan_rag.rag import Augmentation, LLMGeneration, RAGPipeline, Retrieval
from qingchuan_rag.repositories.bm25_repository import BM25Repository
from qingchuan_rag.repositories.document_repository import DocumentRepository
from qingchuan_rag.repositories.vector_repository import VectorRepository
from qingchuan_rag.services.audit_service import AuditService
from qingchuan_rag.services.document_service import DocumentService
from qingchuan_rag.services.rag_service import RAGService
from qingchuan_rag.services.retrieval_adapter import RetrievalAdapter
from qingchuan_rag.services.sync_service import SyncService
from qingchuan_rag.sync.scheduler import SyncScheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 初始化日志配置（全局仅一次；控制台 DEBUG 彩色 / 生产 JSON，文件始终 JSON）
    setup_logging()
    logger.info("Starting x-QingChuan application...")

    # 初始化数据库（审计日志 / 同步任务状态表）
    init_database()
    logger.info("Database initialized successfully")

    # 初始化审计服务
    audit_service = AuditService()

    # 初始化文档存储 Repository层
    doc_repo = DocumentRepository(storage_path="./data/documents")

    # 初始化 BM25 Repository层（稀疏索引）
    bm25_repo = BM25Repository(
        persist_directory="./data/bm25",
        index_name="documents",
    )

    # 初始化向量存储 Repository层（稠密索引）
    vector_repo = VectorRepository(
        persist_directory=settings.VECTOR_STORE_PERSIST_DIR,
        collection_name=settings.VECTOR_STORE_COLLECTION_NAME,
        distance_type=settings.VECTOR_STORE_DISTANCE,
    )

    # 初始化文档服务（同时构建稠密和稀疏索引）
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

    # 初始化 RAG 服务
    retrieval = Retrieval(
        vector_repo=vector_repo,
        bm25_repo=bm25_repo,
    )
    augmentation = Augmentation()
    generation = LLMGeneration(
        default_provider=settings.GENERATION_PROVIDER,
        default_model=settings.GENERATION_MODEL,
        default_temperature=settings.GENERATION_TEMPERATURE,
        default_max_tokens=settings.GENERATION_MAX_TOKENS,
        default_timeout=settings.GENERATION_TIMEOUT,
    )
    pipeline = RAGPipeline(
        retrieval=retrieval,
        augmentation=augmentation,
        generation=generation,
    )
    rag_service = RAGService(pipeline=pipeline, audit_service=audit_service)

    # 初始化人社数据同步服务（触发接口 + APScheduler 周期调度共用同一实例）
    sync_service = SyncService(
        document_service=document_service,
        rag_service=rag_service,
        audit_service=audit_service,
    )
    sync_scheduler = SyncScheduler(
        sync_service=sync_service,
        cron=settings.SYNC_CRON,
        enabled=settings.SYNC_ENABLED,
    )

    # 直接存储到 app.state
    app.state.rag_service = rag_service
    app.state.document_service = document_service
    app.state.audit_service = audit_service
    app.state.sync_service = sync_service
    # 领域协议适配器：供未来 agent-service 以库方式集成（RetrievalPort）
    app.state.retrieval_adapter = RetrievalAdapter(rag_service=rag_service)

    # 将 RAG 服务注入 MCP server，供 /mcp 工具复用同一实例
    bind_rag_service(rag_service)

    # 初始化服务
    rag_service.initialize()
    document_service.initialize()
    sync_service.initialize()

    # 启动周期同步调度（SYNC_ENABLED=true 时注册 cron 任务）
    sync_scheduler.start()
    app.state.sync_scheduler = sync_scheduler

    logger.info("All services initialized successfully")

    # 手动驱动 MCP 子应用生命周期（Starlette Mount 不会级联执行子应用 lifespan；
    # MCP 2.x 的 StreamableHTTPSessionManager 必须经 run() 初始化 task group）
    mcp_app = getattr(app.state, "mcp_app", None)
    if mcp_app is not None:
        async with mcp_app.router.lifespan_context(mcp_app):
            yield
    else:
        yield

    # 关闭服务
    rag_service = getattr(app.state, "rag_service", None)
    document_service = getattr(app.state, "document_service", None)
    sync_service = getattr(app.state, "sync_service", None)
    sync_scheduler = getattr(app.state, "sync_scheduler", None)
    if sync_scheduler:
        sync_scheduler.shutdown()
    if sync_service:
        sync_service.shutdown()
    if rag_service:
        rag_service.shutdown()
    if document_service:
        document_service.shutdown()

    logger.info("Application shutdown complete")


def create_app() -> FastAPI:
    """创建FastAPI应用"""
    app = FastAPI(
        title=settings.APP_NAME,
        description=settings.APP_DESCRIPTION,
        version=settings.APP_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # 配置中间件
    setup_middleware(app)

    # 注册路由
    app.include_router(api_router, prefix=settings.API_PREFIX)

    # 挂载 MCP server（streamable HTTP，默认路径 /mcp）。
    # 注意：MCP 2.x 的 streamable_http_app 内部路由已含 streamable_http_path 前缀，
    # 此处将其置为 "/" 以匹配 Starlette mount 剥离前缀后的子路径 "/"，
    # 否则挂载后请求会 404（/mcp → 子应用 path="/"，Route("/mcp") 不匹配）。
    # 子应用 lifespan（session manager run()）由外层 FastAPI lifespan 手动驱动。
    mcp_app = mcp_server.streamable_http_app(streamable_http_path="/")
    app.state.mcp_app = mcp_app
    app.mount("/mcp", mcp_app)

    # 全局异常处理：所有错误统一走 error_response 封装
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        """应用异常处理器"""
        logger.error(f"Application exception: {exc.message}")
        return error_response(
            request=request,
            code=exc.code,
            message=exc.message,
            data=exc.detail,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """请求验证异常处理器"""
        logger.error(f"Validation error: {exc.errors()}")
        return error_response(
            request=request,
            code=HttpStatus.BAD_REQUEST.value,
            message="Validation failed",
            data=exc.errors(),
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """通用异常处理器"""
        logger.opt(exception=True).error("Unhandled exception occurred")
        return error_response(
            request=request,
            code=HttpStatus.INTERNAL_ERROR.value,
            message="Internal server error",
            data=str(exc) if settings.DEBUG else None,
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """HTTP 异常处理器（统一 404/400/403 等错误格式）"""
        return error_response(
            request=request,
            code=exc.status_code,
            message=exc.detail if isinstance(exc.detail, str) else str(exc.detail),
            data=None if isinstance(exc.detail, str) else exc.detail,
        )

    # 路由未匹配（Starlette 默认直接返回 {"detail": "Not Found"}，不经过异常链），
    # 替换 Router 默认 handler 使 404 也走统一 error_response 封装。
    async def _not_found_handler(scope, receive, send) -> None:
        request = Request(scope)
        response = error_response(
            request=request,
            code=HttpStatus.NOT_FOUND.value,
            message="Not Found",
        )
        await response(scope, receive, send)

    app.router.default = _not_found_handler

    # 根路径
    @app.get("/", tags=["根路径"])
    async def root(request: Request):
        """根路径"""
        return success_response(
            data={
                "name": settings.APP_ID,
                "version": settings.APP_VERSION,
                "description": settings.APP_DESCRIPTION,
                "docs": "/docs",
                "redoc": "/redoc",
                "openapi": "/openapi.json",
            },
            request=request,
        )

    return app


app = create_app()
