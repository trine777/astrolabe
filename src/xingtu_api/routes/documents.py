"""Document CRUD routes."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends

from ..deps import get_service, get_tenant

router = APIRouter()


@router.post("/documents")
def add_documents(
    collection_id: str = Body(...),
    texts: list[str] = Body(...),
    document_ids: Optional[list[str]] = Body(None),
    tenant_id: str = Depends(get_tenant),
):
    service = get_service()
    result = service.add_documents(
        collection_id, texts, created_by="api",
        document_ids=document_ids, tenant_id=tenant_id,
    )
    return result.model_dump()


@router.get("/documents/{document_id}")
def get_document(document_id: str, tenant_id: str = Depends(get_tenant)):
    service = get_service()
    result = service.get_document(document_id)
    if result is None:
        return {"error": f"Document {document_id} not found"}
    return {k: v for k, v in result.items() if not k.startswith("_") and k != "vector"}


@router.post("/documents/batch")
def batch_get_documents(
    document_ids: list[str] = Body(..., embed=True),
    tenant_id: str = Depends(get_tenant),
):
    service = get_service()
    results = service.batch_get_documents(document_ids)
    return [
        {k: v for k, v in r.items() if not k.startswith("_") and k != "vector"}
        for r in results
    ]


@router.post("/documents/query")
def query_documents(
    collection_id: Optional[str] = None,
    tags: Optional[list[str]] = None,
    metadata_filter: Optional[dict] = None,
    content_type: Optional[str] = None,
    created_by: Optional[str] = None,
    created_after: Optional[str] = None,
    created_before: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    tenant_id: str = Depends(get_tenant),
):
    service = get_service()
    results = service.query_documents(
        collection_id=collection_id, tags_filter=tags,
        metadata_filter=metadata_filter, created_after=created_after,
        created_before=created_before, content_type=content_type,
        created_by=created_by, limit=limit, offset=offset,
    )
    return [
        {k: v for k, v in r.items() if not k.startswith("_") and k != "vector"}
        for r in results
    ]
