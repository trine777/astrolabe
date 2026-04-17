"""Collection CRUD routes."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends

from ..deps import get_service, get_tenant

router = APIRouter()


@router.post("/collections")
def create_collection(
    name: str,
    description: str = "",
    collection_type: str = "documents",
    tags: Optional[list[str]] = None,
    tenant_id: str = Depends(get_tenant),
):
    service = get_service()
    return service.create_collection(
        name=name, description=description or None,
        collection_type=collection_type, tags=tags,
        created_by="api", tenant_id=tenant_id,
    )


@router.get("/collections")
def list_collections(
    status: Optional[str] = None,
    collection_type: Optional[str] = None,
    tenant_id: str = Depends(get_tenant),
):
    service = get_service()
    results = service.list_collections(
        status=status, collection_type=collection_type, tenant_id=tenant_id,
    )
    return [
        {k: v for k, v in r.items() if not k.startswith("_")}
        for r in results
    ]


@router.get("/collections/{collection_id}")
def get_collection(collection_id: str, tenant_id: str = Depends(get_tenant)):
    service = get_service()
    result = service.get_collection(collection_id)
    if result is None:
        return {"error": f"Collection {collection_id} not found"}
    return {k: v for k, v in result.items() if not k.startswith("_")}


@router.put("/collections/{collection_id}")
def update_collection(
    collection_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    status: Optional[str] = None,
    tags: Optional[list[str]] = None,
    tenant_id: str = Depends(get_tenant),
):
    service = get_service()
    kwargs = {}
    if name is not None:
        kwargs["name"] = name
    if description is not None:
        kwargs["description"] = description
    if status is not None:
        kwargs["status"] = status
    if tags is not None:
        kwargs["tags"] = tags
    result = service.update_collection(collection_id, **kwargs)
    if result is None:
        return {"error": f"Collection {collection_id} not found"}
    return {k: v for k, v in result.items() if not k.startswith("_")}


@router.delete("/collections/{collection_id}")
def delete_collection(collection_id: str, tenant_id: str = Depends(get_tenant)):
    service = get_service()
    service.delete_collection(collection_id)
    return {"status": "deleted", "collection_id": collection_id}
