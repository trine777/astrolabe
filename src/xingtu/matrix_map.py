"""
Matrix 操作地图 — 基于星图原生 Collection + Document + Relation 的实现

不引入新表：
  Area      → Collection(collection_type="map_area",  tags=["map","area"])
  Room      → Collection(collection_type="map_room",  tags=["map","room"])
  Operation → Document in the room's collection, metadata_json 存 docs 数组
  父子      → Relation(type="contains")
  引用      → Relation(type="references")
  替代      → Relation(type="superseded_by")
  派生      → Relation(type="derived_from")

提供的操作（被 __init__.XingTuService 和 xingtu_api 共享）：
  register_map_area / register_map_room / register_map_operation
  map_overview / map_enter_area / map_get_room / map_get_operation
  map_graph / map_find
"""
from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .store import XingkongzuoStore
    from .events import YinglanxuanEvents

logger = logging.getLogger(__name__)

# collection_type 常量
AREA_TYPE = "map_area"
ROOM_TYPE = "map_room"
MAP_TAG = "map"

# 关系类型（复用 RelationType 允许的值，加新枚举也行）
REL_CONTAINS = "contains"
REL_REFERENCES = "references"
REL_DERIVED_FROM = "derived_from"
REL_SUPERSEDED_BY = "superseded_by"

# operation 文档的 metadata_json 结构示例:
# {
#   "kind": "operation",
#   "docs": [{"type":"curl","title":"...","content":"...","language":"bash"}],
#   "verified_at": "2026-04-21",
#   "verified_by": "claude",
#   "source": "human"
# }


class MatrixMapService:
    """
    Matrix 地图子服务 — 由 XingTuService 持有。
    """

    def __init__(self, store: "XingkongzuoStore", events: "YinglanxuanEvents"):
        self.store = store
        self.events = events

    # ------------------------------------------------------------------
    # 注册（写）
    # ------------------------------------------------------------------

    def register_area(
        self,
        area_id: str,
        title: str,
        summary: str = "",
        tags: Optional[list[str]] = None,
        metadata: Optional[dict] = None,
        tenant_id: str = "default",
    ) -> dict:
        """注册/更新一个 Area。幂等（同 id 的 upsert）。"""
        merged_tags = list({MAP_TAG, "area", *(tags or [])})
        # 用 store.create_collection 的幂等特性（同名同租户返回已有）
        # 但我们要的是"同 id"幂等，不是同 name，所以先看 get_collection
        existing = self.store.get_collection(area_id)
        if existing:
            # 更新
            result = self.store.update_collection(
                area_id,
                description=summary,
                tags=merged_tags,
                metadata_json=json.dumps(metadata or {}, ensure_ascii=False, default=str),
            )
            event = "updated"
        else:
            result = self.store.create_collection(
                id=area_id,
                name=title,
                description=summary,
                collection_type=AREA_TYPE,
                tags=merged_tags,
                created_by="map-register",
                metadata_json=json.dumps(metadata or {}, ensure_ascii=False, default=str),
                tenant_id=tenant_id,
            )
            event = "created"
        self.events.emit(
            event_type=event,
            target_type="collection",
            target_id=area_id,
            description=f"map_area: {title}",
        )
        return result

    def register_room(
        self,
        room_id: str,
        parent_area_id: str,
        title: str,
        room_key: str,
        summary: str = "",
        accepted_task_types: Optional[list[str]] = None,
        tags: Optional[list[str]] = None,
        extra_metadata: Optional[dict] = None,
        tenant_id: str = "default",
    ) -> dict:
        """注册 Room，自动建 Area→Room 的 contains 边。"""
        # 校验 parent area 存在
        parent = self.store.get_collection(parent_area_id)
        if not parent:
            raise ValueError(f"parent area not found: {parent_area_id}")

        meta = {
            "room_key": room_key,
            "accepted_task_types": accepted_task_types or [],
            **(extra_metadata or {}),
        }
        merged_tags = list({MAP_TAG, "room", room_key, *(tags or [])})

        existing = self.store.get_collection(room_id)
        if existing:
            result = self.store.update_collection(
                room_id,
                description=summary,
                tags=merged_tags,
                metadata_json=json.dumps(meta, ensure_ascii=False, default=str),
            )
            event = "updated"
        else:
            result = self.store.create_collection(
                id=room_id,
                name=title,
                description=summary,
                collection_type=ROOM_TYPE,
                tags=merged_tags,
                created_by="map-register",
                metadata_json=json.dumps(meta, ensure_ascii=False, default=str),
                tenant_id=tenant_id,
            )
            event = "created"

        # 建 Area→Room 的 contains 边（幂等）
        self._ensure_relation(parent_area_id, room_id, REL_CONTAINS)

        self.events.emit(
            event_type=event,
            target_type="collection",
            target_id=room_id,
            description=f"map_room: {title} (parent={parent_area_id})",
        )
        return result

    def register_operation(
        self,
        operation_id: str,
        parent_room_id: str,
        title: str,
        docs: list[dict],
        summary: str = "",
        tags: Optional[list[str]] = None,
        verified_at: str = "",
        verified_by: str = "",
        source: str = "human",
        references: Optional[list[str]] = None,
        tenant_id: str = "default",
    ) -> dict:
        """
        注册 Operation（作为 Document 存在 room collection 下）。

        Args:
            docs: [{type, title, content, language?}, ...] 1-3 条
            references: 外部节点 id 列表，自动建 references 边
        """
        if not (1 <= len(docs) <= 3):
            raise ValueError(f"operation {operation_id} docs 数必须 1-3，当前 {len(docs)}")

        parent = self.store.get_collection(parent_room_id)
        if not parent:
            raise ValueError(f"parent room not found: {parent_room_id}")

        metadata = {
            "kind": "operation",
            "docs": docs,
            "verified_at": verified_at,
            "verified_by": verified_by,
            "source": source,
        }
        merged_tags = list({MAP_TAG, "operation", *(tags or [])})

        # 内容 = title + 1 句 summary（用于未来的语义搜索）
        content = title if not summary else f"{title}\n\n{summary}"

        # upsert: 先查，有就 update，没就 add
        existing = self.store.get_document(operation_id)
        if existing:
            result = self.store.update_document(
                operation_id,
                content=content,
                collection_id=parent_room_id,
                tags=merged_tags,
                metadata_json=json.dumps(metadata, ensure_ascii=False, default=str),
            )
            event = "updated"
        else:
            # add_documents 需要完整 doc dict（含 vector）
            from .models import VECTOR_DIM, now_iso
            now = now_iso()
            doc_dict = {
                "id": operation_id,
                "tenant_id": tenant_id,
                "collection_id": parent_room_id,
                "content": content,
                "vector": [0.0] * VECTOR_DIM,  # 零向量；有 embedding provider 时再重算
                "content_type": "text",
                "source_uri": None,
                "tags": merged_tags,
                "metadata_json": json.dumps(metadata, ensure_ascii=False, default=str),
                "created_at": now,
                "updated_at": now,
                "created_by": "map-register",
            }
            self.store.add_documents([doc_dict])
            result = doc_dict
            event = "created"

        # Room→Op 的 contains 边
        self._ensure_relation(parent_room_id, operation_id, REL_CONTAINS)

        # references 边
        if references:
            for target in references:
                self._ensure_relation(operation_id, target, REL_REFERENCES)

        self.events.emit(
            event_type=event,
            target_type="document",
            target_id=operation_id,
            description=f"map_op: {title} (room={parent_room_id}, docs={len(docs)})",
        )
        return result

    def _ensure_relation(
        self,
        source_id: str,
        target_id: str,
        relation_type: str,
        description: str = "",
    ) -> None:
        """幂等建边：同 source+target+type 已存在就跳过。"""
        existing = self.store.get_relations(
            source_id=source_id, relation_type=relation_type,
        )
        for r in existing:
            if r.get("target_id") == target_id:
                return  # already exists
        import uuid
        from .models import Relation, now_iso
        rel = Relation(
            id=str(uuid.uuid4()),
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type,
            description=description or f"map {relation_type}",
            confidence=1.0,
            is_ai_inferred=False,
            is_confirmed=True,
            created_at=now_iso(),
        )
        self.store.create_relation(
            id=rel.id,
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type,
            description=rel.description,
            confidence=1.0,
            is_ai_inferred=False,
        )

    # ------------------------------------------------------------------
    # 查询（读）
    # ------------------------------------------------------------------

    def overview(self, tenant_id: str = "default") -> dict:
        """顶层概览：所有 area + 每个下辖 room 数量。"""
        areas_raw = self.store.list_collections(
            collection_type=AREA_TYPE, tenant_id=tenant_id,
        )
        areas = []
        total_rooms = 0
        total_ops = 0
        for a in areas_raw:
            rooms = self.store.get_relations(source_id=a["id"], relation_type=REL_CONTAINS)
            room_count = len(rooms)
            op_count = 0
            for r in rooms:
                op_count += len(
                    self.store.get_relations(
                        source_id=r["target_id"], relation_type=REL_CONTAINS,
                    )
                )
            areas.append({
                "id": a["id"],
                "title": a["name"],
                "summary": a.get("description", ""),
                "tags": a.get("tags", []),
                "room_count": room_count,
                "operation_count": op_count,
            })
            total_rooms += room_count
            total_ops += op_count

        return {
            "area_count": len(areas),
            "room_count": total_rooms,
            "operation_count": total_ops,
            "areas": sorted(areas, key=lambda x: x["id"]),
        }

    def enter_area(self, area_id: str) -> dict:
        """进入某 Area，看下辖 room 列表。"""
        area = self.store.get_collection(area_id)
        if not area:
            return {"error": f"area not found: {area_id}"}

        room_rels = self.store.get_relations(source_id=area_id, relation_type=REL_CONTAINS)
        rooms = []
        for r in room_rels:
            room = self.store.get_collection(r["target_id"])
            if not room:
                continue
            meta = self._parse_meta(room)
            rooms.append({
                "id": room["id"],
                "title": room["name"],
                "summary": room.get("description", ""),
                "room_key": meta.get("room_key"),
                "accepted_task_types": meta.get("accepted_task_types", []),
            })

        return {
            "area": {
                "id": area["id"],
                "title": area["name"],
                "summary": area.get("description", ""),
                "tags": area.get("tags", []),
            },
            "rooms": sorted(rooms, key=lambda x: x["id"]),
        }

    def get_room(self, room_id: str) -> dict:
        """某 Room 详情 + 下辖 operation 标题列表。"""
        room = self.store.get_collection(room_id)
        if not room:
            return {"error": f"room not found: {room_id}"}

        meta = self._parse_meta(room)
        op_rels = self.store.get_relations(source_id=room_id, relation_type=REL_CONTAINS)
        operations = []
        for r in op_rels:
            op = self.store.get_document(r["target_id"])
            if not op:
                continue
            op_meta = self._parse_meta(op)
            operations.append({
                "id": op["id"],
                "title": op.get("content", "").split("\n")[0],
                "doc_count": len(op_meta.get("docs", []) or []),
            })

        # 反查 parent area
        parent_rels = self.store.get_relations(target_id=room_id, relation_type=REL_CONTAINS)
        parent_area_id = parent_rels[0]["source_id"] if parent_rels else None

        return {
            "room": {
                "id": room["id"],
                "title": room["name"],
                "summary": room.get("description", ""),
                "room_key": meta.get("room_key"),
                "accepted_task_types": meta.get("accepted_task_types", []),
                "tags": room.get("tags", []),
                "parent_area_id": parent_area_id,
            },
            "operations": sorted(operations, key=lambda x: x["id"]),
        }

    def get_operation(self, operation_id: str) -> dict:
        """Operation 详情（含 docs 正文）。"""
        op = self.store.get_document(operation_id)
        if not op:
            return {"error": f"operation not found: {operation_id}"}

        meta = self._parse_meta(op)
        # 反查 parent room
        parent_rels = self.store.get_relations(target_id=operation_id, relation_type=REL_CONTAINS)
        parent_room_id = parent_rels[0]["source_id"] if parent_rels else None

        return {
            "id": op["id"],
            "title": op.get("content", "").split("\n")[0],
            "summary": "\n".join(op.get("content", "").split("\n")[1:]).strip(),
            "parent_room_id": parent_room_id,
            "docs": meta.get("docs", []),
            "verified_at": meta.get("verified_at"),
            "verified_by": meta.get("verified_by"),
            "source": meta.get("source"),
            "tags": op.get("tags", []),
        }

    def graph(
        self,
        node_id: str,
        max_hops: int = 1,
        relation_types: Optional[list[str]] = None,
    ) -> dict:
        """
        返回节点的出入边。多跳用 max_hops 控制（BFS）。
        """
        visited: set[str] = set()
        frontier: list[str] = [node_id]
        all_edges: list[dict] = []

        for _ in range(max_hops):
            next_frontier: list[str] = []
            for nid in frontier:
                if nid in visited:
                    continue
                visited.add(nid)
                out = self.store.get_relations(source_id=nid) or []
                inb = self.store.get_relations(target_id=nid) or []
                for r in out + inb:
                    if relation_types and r.get("relation_type") not in relation_types:
                        continue
                    edge = {
                        "source_id": r["source_id"],
                        "target_id": r["target_id"],
                        "type": r["relation_type"],
                        "confidence": r.get("confidence", 1.0),
                    }
                    if edge not in all_edges:
                        all_edges.append(edge)
                    next_frontier.append(r["source_id"])
                    next_frontier.append(r["target_id"])
            frontier = [n for n in next_frontier if n not in visited]

        return {
            "center": node_id,
            "max_hops": max_hops,
            "node_count": len(visited) + len(set(frontier)),
            "edge_count": len(all_edges),
            "edges": all_edges,
        }

    def find(self, query: str, limit: int = 10) -> list[dict]:
        """
        按标题/summary/tag 找 operation。走简单 substring 匹配。
        （未来可接 hybrid_search 做语义）
        """
        q = query.lower()
        results: list[dict] = []

        # 扫所有 map_room 下的 document (operation)
        rooms = self.store.list_collections(collection_type=ROOM_TYPE)
        for room in rooms:
            docs = self.store.list_documents(collection_id=room["id"], limit=1000)
            for d in docs:
                content = str(d.get("content", "")).lower()
                tags = [str(t).lower() for t in (d.get("tags") or [])]
                meta = self._parse_meta(d)
                if q in content or any(q in t for t in tags):
                    results.append({
                        "id": d["id"],
                        "title": d.get("content", "").split("\n")[0],
                        "room_id": room["id"],
                        "room_title": room["name"],
                        "tags": d.get("tags", []),
                        "doc_count": len(meta.get("docs", []) or []),
                    })
                    if len(results) >= limit:
                        return results
        return results

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_meta(obj: dict) -> dict:
        raw = obj.get("metadata_json") or "{}"
        try:
            return json.loads(raw) if isinstance(raw, str) else raw
        except (ValueError, TypeError):
            return {}
