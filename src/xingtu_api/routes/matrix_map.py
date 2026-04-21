"""
Matrix 操作地图 REST 路由

基于 service.matrix_map 子服务，零新表（复用 Collection/Document/Relation）。

端点：
  POST /api/v1/matrix-map/areas              注册 Area
  POST /api/v1/matrix-map/rooms              注册 Room
  POST /api/v1/matrix-map/operations         注册 Operation
  POST /api/v1/matrix-map/bulk-register      一次注册全量（bootstrap）

  GET  /api/v1/matrix-map/overview           顶层 6 area 概览
  GET  /api/v1/matrix-map/areas/{area_id}    某区 + 下辖 room
  GET  /api/v1/matrix-map/rooms/{room_id}    某 room + operations
  GET  /api/v1/matrix-map/operations/{op_id} op 详情 + docs
  GET  /api/v1/matrix-map/graph/{node_id}    节点的出入边（图）
  GET  /api/v1/matrix-map/find?q=...         按标题/tag 搜索 operation
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..deps import get_service, get_tenant

router = APIRouter(prefix="/matrix-map", tags=["matrix-map"])


# ===== 请求模型 =====


class AreaPayload(BaseModel):
    id: str
    title: str
    summary: str = ""
    tags: Optional[list[str]] = None
    metadata: Optional[dict] = None


class RoomPayload(BaseModel):
    id: str
    parent_area_id: str
    title: str
    room_key: str
    summary: str = ""
    accepted_task_types: Optional[list[str]] = None
    tags: Optional[list[str]] = None
    extra_metadata: Optional[dict] = None


class OperationDoc(BaseModel):
    type: str = Field(description="curl | rule | checklist | diagram | payload")
    title: str
    content: str
    language: Optional[str] = None


class OperationPayload(BaseModel):
    id: str
    parent_room_id: str
    title: str
    docs: list[OperationDoc]
    summary: str = ""
    tags: Optional[list[str]] = None
    verified_at: str = ""
    verified_by: str = ""
    source: str = "human"
    references: Optional[list[str]] = None


class BulkRegisterPayload(BaseModel):
    areas: list[AreaPayload] = Field(default_factory=list)
    rooms: list[RoomPayload] = Field(default_factory=list)
    operations: list[OperationPayload] = Field(default_factory=list)


# ===== 写 =====


@router.post("/areas")
def register_area(body: AreaPayload, tenant_id: str = Depends(get_tenant)):
    service = get_service()
    return service.matrix_map.register_area(
        area_id=body.id,
        title=body.title,
        summary=body.summary,
        tags=body.tags,
        metadata=body.metadata,
        tenant_id=tenant_id,
    )


@router.post("/rooms")
def register_room(body: RoomPayload, tenant_id: str = Depends(get_tenant)):
    service = get_service()
    try:
        return service.matrix_map.register_room(
            room_id=body.id,
            parent_area_id=body.parent_area_id,
            title=body.title,
            room_key=body.room_key,
            summary=body.summary,
            accepted_task_types=body.accepted_task_types,
            tags=body.tags,
            extra_metadata=body.extra_metadata,
            tenant_id=tenant_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/operations")
def register_operation(body: OperationPayload, tenant_id: str = Depends(get_tenant)):
    service = get_service()
    try:
        return service.matrix_map.register_operation(
            operation_id=body.id,
            parent_room_id=body.parent_room_id,
            title=body.title,
            docs=[d.model_dump() for d in body.docs],
            summary=body.summary,
            tags=body.tags,
            verified_at=body.verified_at,
            verified_by=body.verified_by,
            source=body.source,
            references=body.references,
            tenant_id=tenant_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/bulk-register")
def bulk_register(body: BulkRegisterPayload, tenant_id: str = Depends(get_tenant)):
    """一次注册 area + room + operation（bootstrap 用）。"""
    service = get_service()
    result = {"areas": 0, "rooms": 0, "operations": 0, "errors": []}

    for a in body.areas:
        try:
            service.matrix_map.register_area(
                area_id=a.id, title=a.title, summary=a.summary,
                tags=a.tags, metadata=a.metadata, tenant_id=tenant_id,
            )
            result["areas"] += 1
        except Exception as e:
            result["errors"].append(f"area {a.id}: {e}")

    for r in body.rooms:
        try:
            service.matrix_map.register_room(
                room_id=r.id, parent_area_id=r.parent_area_id, title=r.title,
                room_key=r.room_key, summary=r.summary,
                accepted_task_types=r.accepted_task_types, tags=r.tags,
                extra_metadata=r.extra_metadata, tenant_id=tenant_id,
            )
            result["rooms"] += 1
        except Exception as e:
            result["errors"].append(f"room {r.id}: {e}")

    for o in body.operations:
        try:
            service.matrix_map.register_operation(
                operation_id=o.id, parent_room_id=o.parent_room_id, title=o.title,
                docs=[d.model_dump() for d in o.docs], summary=o.summary,
                tags=o.tags, verified_at=o.verified_at, verified_by=o.verified_by,
                source=o.source, references=o.references, tenant_id=tenant_id,
            )
            result["operations"] += 1
        except Exception as e:
            result["errors"].append(f"operation {o.id}: {e}")

    return result


# ===== 读 =====


@router.get("/overview")
def overview(tenant_id: str = Depends(get_tenant)):
    service = get_service()
    return service.matrix_map.overview(tenant_id=tenant_id)


@router.get("/areas/{area_id}")
def get_area(area_id: str):
    service = get_service()
    result = service.matrix_map.enter_area(area_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/rooms/{room_id}")
def get_room(room_id: str):
    service = get_service()
    result = service.matrix_map.get_room(room_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/operations/{op_id}")
def get_operation(op_id: str):
    service = get_service()
    result = service.matrix_map.get_operation(op_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/graph/{node_id}")
def get_graph(
    node_id: str,
    max_hops: int = 1,
    relation_types: Optional[str] = None,
):
    """
    节点图视图。

    Args:
        max_hops: BFS 深度 (1-3)
        relation_types: 逗号分隔的类型过滤，如 "contains,references"
    """
    service = get_service()
    types = [t.strip() for t in relation_types.split(",")] if relation_types else None
    if max_hops < 1 or max_hops > 3:
        raise HTTPException(status_code=422, detail="max_hops 必须 1-3")
    return service.matrix_map.graph(node_id=node_id, max_hops=max_hops, relation_types=types)


@router.get("/find")
def find(q: str, limit: int = 10):
    if not q:
        raise HTTPException(status_code=422, detail="q 不能为空")
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=422, detail="limit 必须 1-100")
    service = get_service()
    return service.matrix_map.find(query=q, limit=limit)
