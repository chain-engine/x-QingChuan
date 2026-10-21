#!/usr/bin/env python3
"""
RAG API Module

RAG查询接口 - 仅负责参数接收、调用业务服务、标准化返回
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from qingchuan_rag.core.exceptions import GenerationError, RetrievalError
from qingchuan_rag.core.logger import logger
from qingchuan_rag.http_server.dependencies import (
    get_app_operator_context,
    get_rag_service,
)
from qingchuan_rag.http_server.response import success_response
from qingchuan_rag.schemas.rag import (
    EmbeddingRequest,
    RAGQueryRequest,
    RetrievalRequest,
    from_search_results,
)
from qingchuan_rag.schemas.responses import ResponseModel
from qingchuan_rag.services.rag_service import RAGService

router = APIRouter()


@router.post(
    "/rag/query",
    summary="RAG查询",
    description="使用RAG进行问答，检索相关文档并生成答案",
    tags=["RAG"],
    response_model=ResponseModel,
)
async def rag_query(
    request: Request,
    body: RAGQueryRequest,
    rag_service: RAGService = Depends(get_rag_service),
) -> dict[str, Any]:
    """RAG查询接口"""
    try:
        operator = get_app_operator_context(request)
        result = await rag_service.query(
            query=body.query,
            top_k=body.top_k,
            similarity_threshold=body.similarity_threshold,
            use_mmr=body.use_mmr,
            mmr_lambda=body.mmr_lambda,
            metadata_filter=body.metadata_filter,
            provider=body.provider,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
            operator=operator,
        )

        return success_response(data=result, request=request)

    except (RetrievalError, GenerationError) as e:
        logger.exception("RAG service error")
        raise HTTPException(status_code=500, detail=str(e)) from e
    except Exception as e:
        logger.exception("RAG query error")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post(
    "/rag/retrieve",
    summary="文本检索",
    description="通过文本检索相关文档，不进行生成",
    tags=["RAG"],
    response_model=ResponseModel,
)
async def retrieve_docs(
    request: Request,
    body: RetrievalRequest,
    rag_service: RAGService = Depends(get_rag_service),
) -> dict[str, Any]:
    """文本检索接口"""
    try:
        operator = get_app_operator_context(request)
        documents = rag_service.retrieve(
            query=body.query,
            top_k=body.top_k,
            similarity_threshold=body.similarity_threshold,
            use_mmr=body.use_mmr,
            mmr_lambda=body.mmr_lambda,
            metadata_filter=body.metadata_filter,
            operator=operator,
        )

        # 复用 from_search_results 统一组装（与 MCP 层共用，输出领域契约 RetrievedChunk）
        retrieved_docs = from_search_results(documents)

        data = {
            "query": body.query,
            "documents": [doc.model_dump() for doc in retrieved_docs],
            "total": len(retrieved_docs),
        }
        return success_response(data=data, request=request)

    except RetrievalError as e:
        logger.exception("Retrieval error")
        raise HTTPException(status_code=500, detail=str(e)) from e
    except Exception as e:
        logger.exception("Retrieve error")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post(
    "/rag/embed",
    summary="文本向量化",
    description="将文本转换为向量表示",
    tags=["RAG"],
    response_model=ResponseModel,
)
async def embed_text(
    request: Request,
    body: EmbeddingRequest,
    rag_service: RAGService = Depends(get_rag_service),
) -> dict[str, Any]:
    """文本向量化接口"""
    try:
        operator = get_app_operator_context(request)
        embeddings = rag_service.encode(
            texts=body.texts,
            normalize=body.normalize,
        )
        stats = rag_service.get_embedding_stats(operator=operator)

        data = {
            "embeddings": embeddings,
            "dimension": stats.get("dimension"),
            "model": stats.get("model"),
        }
        return success_response(data=data, request=request)

    except Exception as e:
        logger.error(f"Embed error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get(
    "/rag/stats",
    summary="RAG统计",
    description="获取RAG系统统计信息",
    tags=["RAG"],
    response_model=ResponseModel,
)
async def get_rag_stats(
    request: Request,
    rag_service: RAGService = Depends(get_rag_service),
) -> dict[str, Any]:
    """获取RAG统计信息"""
    try:
        operator = get_app_operator_context(request)
        stats = rag_service.get_stats(operator=operator)
        vector_count = stats.get("vector_count", 0)

        data = {
            "vector_count": vector_count,
            "status": "running",
        }
        return success_response(data=data, request=request)

    except Exception as e:
        logger.error(f"Get stats error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e
