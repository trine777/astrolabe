"""Metric CRUD + calculate routes."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException

from ..deps import get_service, get_tenant
from xingtu.metrics import FormulaError

router = APIRouter()


def _clean(d: dict) -> dict:
    return {k: v for k, v in d.items() if not k.startswith("_")}


@router.post("/metrics")
def create_metric(
    name: str = Body(...),
    formula: dict = Body(...),
    kind: str = Body("scalar"),
    description: str = Body(""),
    unit: str = Body(""),
    tags: Optional[list[str]] = Body(None),
    tenant_id: str = Depends(get_tenant),
):
    service = get_service()
    try:
        result = service.create_metric(
            name=name,
            formula=formula,
            kind=kind,
            description=description or None,
            unit=unit or None,
            tags=tags,
            created_by="api",
            tenant_id=tenant_id,
        )
    except FormulaError as e:
        raise HTTPException(status_code=400, detail=f"formula_invalid: {e}")
    return _clean(result)


@router.get("/metrics")
def list_metrics(
    status: Optional[str] = None,
    tenant_id: str = Depends(get_tenant),
):
    service = get_service()
    results = service.list_metrics(status=status, tenant_id=tenant_id)
    return [_clean(r) for r in results]


@router.get("/metrics/{metric_id}")
def get_metric(metric_id: str, tenant_id: str = Depends(get_tenant)):
    service = get_service()
    result = service.get_metric(metric_id)
    if result is None:
        raise HTTPException(status_code=404, detail="metric not found")
    return _clean(result)


@router.put("/metrics/{metric_id}")
def update_metric(
    metric_id: str,
    name: Optional[str] = Body(None),
    formula: Optional[dict] = Body(None),
    status: Optional[str] = Body(None),
    description: Optional[str] = Body(None),
    unit: Optional[str] = Body(None),
    tenant_id: str = Depends(get_tenant),
):
    service = get_service()
    updates = {}
    if name is not None:
        updates["name"] = name
    if formula is not None:
        updates["formula"] = formula
    if status is not None:
        updates["status"] = status
    if description is not None:
        updates["description"] = description
    if unit is not None:
        updates["unit"] = unit
    try:
        result = service.update_metric(metric_id, **updates)
    except FormulaError as e:
        raise HTTPException(status_code=400, detail=f"formula_invalid: {e}")
    if result is None:
        raise HTTPException(status_code=404, detail="metric not found")
    return _clean(result)


@router.delete("/metrics/{metric_id}")
def delete_metric(metric_id: str, tenant_id: str = Depends(get_tenant)):
    service = get_service()
    deleted = service.delete_metric(metric_id)
    return {"deleted": deleted, "metric_id": metric_id}


@router.post("/metrics/{metric_id}/calculate")
def calculate_metric(
    metric_id: str,
    persist: bool = True,
    tenant_id: str = Depends(get_tenant),
):
    service = get_service()
    try:
        result = service.calculate_metric(
            metric_id, persist=persist, tenant_id=tenant_id
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {
        "metric": _clean(result["metric"]),
        "result": result["result"],
    }


@router.post("/metrics/calculate/batch")
def calculate_batch(
    metric_ids: list[str] = Body(..., embed=True),
    persist: bool = Body(True),
    tenant_id: str = Depends(get_tenant),
):
    service = get_service()
    results = service.calculate_metrics_batch(
        metric_ids, persist=persist, tenant_id=tenant_id
    )
    out = []
    for r in results:
        metric = r.get("metric", {})
        out.append({
            "metric": _clean(metric) if isinstance(metric, dict) else metric,
            "result": r.get("result", {}),
        })
    return out


@router.get("/metrics/{metric_id}/history")
def get_history(
    metric_id: str,
    limit: int = 100,
    since: Optional[str] = None,
    until: Optional[str] = None,
    tenant_id: str = Depends(get_tenant),
):
    service = get_service()
    return service.get_metric_history(
        metric_id, limit=limit, since=since, until=until
    )
