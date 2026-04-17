"""Search routes."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends

from ..deps import get_service, get_tenant

router = APIRouter()


@router.post("/search/vector")
def vector_search(
    query: str,
    collection_id: Optional[str] = None,
    limit: int = 10,
    tenant_id: str = Depends(get_tenant),
):
    service = get_service()
    return service.search(query, search_type="vector", collection_id=collection_id, limit=limit)


@router.post("/search/text")
def text_search(
    query: str,
    collection_id: Optional[str] = None,
    limit: int = 10,
    tenant_id: str = Depends(get_tenant),
):
    service = get_service()
    return service.search(query, search_type="text", collection_id=collection_id, limit=limit)


@router.post("/search/hybrid")
def hybrid_search(
    query: str,
    collection_id: Optional[str] = None,
    limit: int = 10,
    reranker: str = "rrf",
    tenant_id: str = Depends(get_tenant),
):
    service = get_service()
    return service.search(
        query, search_type="hybrid", collection_id=collection_id,
        limit=limit, reranker=reranker,
    )
