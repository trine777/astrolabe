"""Trust evaluation routes."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends

from ..deps import get_service, get_tenant

router = APIRouter()


@router.get("/trust/{item_id}")
def evaluate_trust(item_id: str, tenant_id: str = Depends(get_tenant)):
    service = get_service()
    return service.evaluate_trust(item_id)


@router.post("/trust/batch")
def batch_evaluate_trust(
    item_ids: list[str] = Body(..., embed=True),
    tenant_id: str = Depends(get_tenant),
):
    service = get_service()
    return service.batch_evaluate_trust(item_ids)
