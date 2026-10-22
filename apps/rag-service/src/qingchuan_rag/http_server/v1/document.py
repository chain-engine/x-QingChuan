#!/usr/bin/env python3
"""
Document API Module

文档管理接口 - 仅负责参数接收、调用业务服务、标准化返回
"""

import json
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from qingchuan_rag.core.exceptions import DocumentError, ValidationError
from qingchuan_rag.core.logger import logger
from qingchuan_rag.http_server.dependencies import (
    get_app_operator_context,
    get_document_service,
)
from qingchuan_rag.http_server.response import success_response
from qingchuan_rag.infras.parsers import decode_text_content, extract_pdf_text
from qingchuan_rag.schemas.responses import ResponseModel
from qingchuan_rag.services.document_service import DocumentService

router = APIRouter()


@router.post(
    "/documents/upload",
    summary="文档上传",
    description="上传文档并自动进行索引",
    tags=["文档"],
    response_model=ResponseModel,
)
async def upload_document(
    request: Request,
    file: UploadFile = File(..., description="上传的文件"),
    metadata: str = Form("{}", description="文档元数据（JSON字符串）"),
    document_service: DocumentService = Depends(get_document_service),
) -> dict[str, Any]:
    """文档上传接口"""
    try:
        meta = _parse_metadata(metadata)

        content = await file.read()

        file_name = file.filename or "unknown"
        file_type = file_name.split(".")[-1].lower() if "." in file_name else "txt"

        # 按文件类型解析：PDF 走 PyMuPDF 文本提取；其余按文本文件解码（utf-8 / gbk）
        text = extract_pdf_text(content) if file_type == "pdf" else decode_text_content(content)

        operator = get_app_operator_context(request)
        result = document_service.upload_document(
            text=text,
            file_name=file_name,
            file_type=file_type,
            file_size=len(content),
            metadata=meta,
            operator=operator,
            file_content=content,
        )

        data = {
            "document_id": result["document_id"],
            "file_name": file_name,
            "status": result["status"],
            "chunk_count": result["chunk_count"],
            "message": "Document uploaded and indexed successfully",
        }
        return success_response(data=data, request=request)

    except ValidationError as e:
        logger.error(f"[{e.__class__.__name__}] {e.message}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e)) from e
    except DocumentError as e:
        logger.error(f"[{e.__class__.__name__}] {e.message}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("Upload error")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get(
    "/documents",
    summary="文档列表",
    description="获取文档列表（支持分页）",
    tags=["文档"],
    response_model=ResponseModel,
)
async def list_documents(
    request: Request,
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    file_type: str | None = None,
    document_service: DocumentService = Depends(get_document_service),
) -> dict[str, Any]:
    """文档列表接口（支持分页）"""
    try:
        page = max(1, page)
        page_size = min(max(1, page_size), 100)

        skip = (page - 1) * page_size

        operator = get_app_operator_context(request)
        result = document_service.list_documents(
            status=status,
            file_type=file_type,
            skip=skip,
            limit=page_size,
            operator=operator,
        )

        documents = result["documents"]
        total = result["total"]
        total_pages = (total + page_size - 1) // page_size

        doc_infos = [
            {
                "document_id": doc.get("document_id"),
                "file_name": doc.get("file_name"),
                "file_type": doc.get("file_type"),
                "file_size": doc.get("file_size", 0),
                "status": doc.get("status"),
                "chunk_count": doc.get("chunk_count", 0),
                "created_at": doc.get("created_at"),
                "updated_at": doc.get("updated_at"),
                "metadata": doc.get("metadata", {}),
            }
            for doc in documents
        ]

        data = {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "items": doc_infos,
        }
        return success_response(data=data, request=request)

    except Exception as e:
        logger.error(f"列出文档失败: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get(
    "/documents/{document_id}",
    summary="获取文档详情",
    description="获取指定文档的详细信息",
    tags=["文档"],
    response_model=ResponseModel,
)
async def get_document(
    request: Request,
    document_id: str,
    document_service: DocumentService = Depends(get_document_service),
) -> dict[str, Any]:
    """获取文档详情接口"""
    try:
        operator = get_app_operator_context(request)
        document = document_service.get_document(document_id, operator=operator)

        if document.get("status") == "not_found":
            raise HTTPException(status_code=404, detail="文档不存在")

        return success_response(data=document, request=request)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get document error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.delete(
    "/documents/{document_id}",
    summary="删除文档",
    description="删除指定文档及其关联的向量",
    tags=["文档"],
    response_model=ResponseModel,
)
async def delete_document(
    request: Request,
    document_id: str,
    document_service: DocumentService = Depends(get_document_service),
) -> dict[str, Any]:
    """删除文档接口"""
    try:
        operator = get_app_operator_context(request)
        result = document_service.delete_document(document_id, operator=operator)

        data = {
            "document_id": result["document_id"],
            "status": result["status"],
            "vector_count": result["vector_count"],
            "message": "文档删除成功",
        }
        return success_response(data=data, request=request)

    except DocumentError as e:
        logger.error(f"[{e.__class__.__name__}] {e.message}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("Delete document error")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get(
    "/documents/{document_id}/status",
    summary="获取文档状态",
    description="获取指定文档的处理状态",
    tags=["文档"],
    response_model=ResponseModel,
)
async def get_document_status(
    request: Request,
    document_id: str,
    document_service: DocumentService = Depends(get_document_service),
) -> dict[str, Any]:
    """获取文档状态接口"""
    try:
        operator = get_app_operator_context(request)
        status = document_service.get_document_status(document_id, operator=operator)

        if status.get("status") == "not_found":
            raise HTTPException(status_code=404, detail="文档不存在")

        return success_response(data=status, request=request)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get document status error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


def _parse_metadata(metadata: str) -> dict[str, Any]:
    """解析元数据JSON"""
    try:
        return json.loads(metadata) if metadata else {}
    except json.JSONDecodeError as e:
        raise ValidationError("Invalid metadata JSON format") from e
