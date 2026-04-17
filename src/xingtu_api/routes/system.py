"""System routes — stats, events, optimize, projections."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends

from ..deps import get_service, get_tenant

router = APIRouter()


@router.get("/stats")
def get_stats(tenant_id: str = Depends(get_tenant)):
    service = get_service()
    return service.get_stats()


@router.get("/events")
def get_events(
    target_id: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = 50,
    tenant_id: str = Depends(get_tenant),
):
    service = get_service()
    return service.get_events(target_id=target_id, event_type=event_type, limit=limit)


@router.post("/optimize")
def optimize(tenant_id: str = Depends(get_tenant)):
    service = get_service()
    return service.optimize()


@router.get("/world-model")
def get_world_model(tenant_id: str = Depends(get_tenant)):
    service = get_service()
    return service.get_world_model()


@router.get("/projection/l0")
def projection_l0(
    limit: int = 20, offset: int = 0,
    tenant_id: str = Depends(get_tenant),
):
    service = get_service()
    return service.projection_l0(limit=limit, offset=offset)


@router.get("/projection/l1/{collection_id}")
def projection_l1(
    collection_id: str, limit: int = 30, offset: int = 0,
    tenant_id: str = Depends(get_tenant),
):
    service = get_service()
    return service.projection_l1(collection_id, limit=limit, offset=offset)


@router.get("/projection/l2/{document_id}")
def projection_l2(document_id: str, tenant_id: str = Depends(get_tenant)):
    service = get_service()
    return service.projection_l2(document_id)
