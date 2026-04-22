"""
星图 XingTu - 星空座存储层

XingkongzuoStore: 基于 LanceDB 的多模态数据存储引擎。
管理集合、文档、关系、事件和 Agent 记忆的完整生命周期。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Union

import lancedb
import lancedb.table

from .config import StoreConfig
from .models import (
    AgentMemory,
    Collection,
    Document,
    Event,
    Metric,
    MetricResult,
    Relation,
    UniverseDelta,
    UniverseGoal,
    WorldModel,
    now_iso,
)

logger = logging.getLogger(__name__)


def _esc(value: str) -> str:
    """Escape single quotes for LanceDB SQL where clauses."""
    if value is None:
        return ""
    return str(value).replace("'", "''")


class XingkongzuoStore:
    """
    星空座存储 - 星图的 LanceDB 存储层

    负责所有数据的持久化：集合、文档、关系、事件、Agent 记忆。
    支持向量搜索、全文检索和结构化查询。
    """

    def __init__(self, db_path: Union[str, StoreConfig] = "~/.xingtu/data"):
        if isinstance(db_path, StoreConfig):
            resolved = db_path.resolved_path
        else:
            resolved = Path(db_path).expanduser()
        resolved.mkdir(parents=True, exist_ok=True)
        self.db = lancedb.connect(str(resolved))
        self._tables: dict[str, lancedb.table.Table] = {}

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """Create all tables if they don't exist."""
        table_schemas: dict = {
            "collections": Collection,
            "documents": Document,
            "relations": Relation,
            "events": Event,
            "agent_memories": AgentMemory,
            "universe_goals": UniverseGoal,
            "universe_deltas": UniverseDelta,
            "metrics": Metric,
            "metric_results": MetricResult,
        }
        for name, model in table_schemas.items():
            try:
                self._tables[name] = self.db.open_table(name)
                logger.debug("Opened existing table: %s", name)
            except Exception:
                self._tables[name] = self.db.create_table(
                    name, schema=model.to_arrow_schema()
                )
                logger.info("Created table: %s", name)

    def get_table(self, name: str) -> lancedb.table.Table:
        """Get a table reference by name, opening it if necessary."""
        if name not in self._tables:
            self._tables[name] = self.db.open_table(name)
        return self._tables[name]

    # ------------------------------------------------------------------
    # Collection CRUD
    # ------------------------------------------------------------------

    def get_collection_by_name(
        self,
        name: str,
        tenant_id: str = "default",
        collection_type: Optional[str] = None,
    ) -> Optional[dict]:
        """Find a collection by (name, tenant, [collection_type]). Returns first match or None.

        If collection_type is given, only matches that type. 这允许不同 type 下同名
        (如 map_area '系统治理' 和 map_organ '系统治理' 共存).
        """
        table = self.get_table("collections")
        conditions = [
            f"name = '{_esc(name)}'",
            f"tenant_id = '{_esc(tenant_id)}'",
        ]
        if collection_type:
            conditions.append(f"collection_type = '{_esc(collection_type)}'")
        results = (
            table.search()
            .where(" AND ".join(conditions), prefilter=True)
            .limit(1)
            .to_list()
        )
        return results[0] if results else None

    def create_collection(
        self,
        id: str,
        name: str,
        description: Optional[str] = None,
        collection_type: str = "documents",
        tags: Optional[list[str]] = None,
        created_by: str = "system",
        metadata_json: Optional[str] = None,
        tenant_id: str = "default",
    ) -> dict:
        """Create a new collection. Returns existing if (name, tenant, type) matches.

        幂等键: (name, tenant_id, collection_type). 不同 type 下可同名
        (如 area + organ 用同一 title 不冲突).
        """
        existing = self.get_collection_by_name(
            name, tenant_id=tenant_id, collection_type=collection_type,
        )
        if existing:
            return {k: v for k, v in existing.items() if not k.startswith("_")}

        now = now_iso()
        collection = Collection(
            id=id,
            tenant_id=tenant_id,
            name=name,
            description=description,
            collection_type=collection_type,
            status="draft",
            tags=tags or [],
            item_count=0,
            created_at=now,
            updated_at=now,
            created_by=created_by,
            metadata_json=metadata_json,
        )
        table = self.get_table("collections")
        table.add([collection.model_dump()])
        return collection.model_dump()

    def get_collection(self, id: str) -> Optional[dict]:
        """Retrieve a single collection by ID."""
        table = self.get_table("collections")
        results = (
            table.search()
            .where(f"id = '{_esc(id)}'", prefilter=True)
            .limit(1)
            .to_list()
        )
        return results[0] if results else None

    def list_collections(
        self,
        status: Optional[str] = None,
        collection_type: Optional[str] = None,
        tenant_id: str = "default",
    ) -> list[dict]:
        """List collections with optional filters."""
        table = self.get_table("collections")
        query = table.search()
        conditions: list[str] = [f"tenant_id = '{_esc(tenant_id)}'"]
        if status:
            conditions.append(f"status = '{_esc(status)}'")
        if collection_type:
            conditions.append(f"collection_type = '{_esc(collection_type)}'")
        query = query.where(" AND ".join(conditions), prefilter=True)
        return query.limit(1000).to_list()

    def update_collection(self, id: str, **kwargs) -> Optional[dict]:
        """
        Update collection fields.

        Supported: name, description, status, tags, item_count, metadata_json.
        Uses delete-then-add pattern required by LanceDB.
        """
        existing = self.get_collection(id)
        if not existing:
            return None
        kwargs["updated_at"] = now_iso()
        table = self.get_table("collections")
        table.delete(f"id = '{_esc(id)}'")
        existing.update(kwargs)
        # Clean up any non-schema fields that might come from search results
        for key in list(existing.keys()):
            if key.startswith("_"):
                del existing[key]
        table.add([existing])
        return existing

    def delete_collection(self, id: str) -> bool:
        """Delete a collection and all its documents."""
        table = self.get_table("collections")
        table.delete(f"id = '{_esc(id)}'")
        # Also delete all documents in this collection
        doc_table = self.get_table("documents")
        doc_table.delete(f"collection_id = '{_esc(id)}'")
        return True

    # ------------------------------------------------------------------
    # Document CRUD
    # ------------------------------------------------------------------

    def add_documents(self, docs: list[dict], tenant_id: str = "default") -> int:
        """Add documents (as dicts with all Document fields including vector).

        Uses upsert semantics for custom IDs: deletes existing docs with
        matching IDs before adding, preventing phantom duplicates.
        Returns count of documents added.
        """
        if not docs:
            return 0
        # Inject tenant_id if not present in each doc
        for d in docs:
            d.setdefault("tenant_id", tenant_id)
        table = self.get_table("documents")
        # Upsert: remove existing docs with same IDs to prevent duplicates
        existing_ids = [d["id"] for d in docs if d.get("id")]
        if existing_ids:
            escaped = ", ".join(f"'{_esc(i)}'" for i in existing_ids)
            try:
                table.delete(f"id IN ({escaped})")
            except Exception:
                pass  # Table might be empty or IDs don't exist yet
        table.add(docs)
        return len(docs)

    def get_document(self, id: str) -> Optional[dict]:
        """Retrieve a single document by ID."""
        table = self.get_table("documents")
        results = (
            table.search()
            .where(f"id = '{_esc(id)}'", prefilter=True)
            .limit(1)
            .to_list()
        )
        return results[0] if results else None

    def get_documents_batch(self, ids: list[str], max_batch: int = 1000) -> list[dict]:
        """Retrieve multiple documents by ID list.

        Efficient batch fetch — uses IN clause instead of N individual queries.
        Auto-deduplicates IDs; silently skips missing IDs.
        Caps at max_batch (default 1000) per call to prevent SQL parser overload.
        For larger sets, the caller should chunk.
        """
        if not ids:
            return []
        # Deduplicate and filter empty strings, preserving order
        seen = set()
        clean_ids = []
        for i in ids:
            if i and i not in seen:
                seen.add(i)
                clean_ids.append(i)
        if not clean_ids:
            return []
        if len(clean_ids) > max_batch:
            logger.warning(
                "get_documents_batch: %d IDs exceeds max %d, truncating",
                len(clean_ids), max_batch,
            )
            clean_ids = clean_ids[:max_batch]

        table = self.get_table("documents")
        escaped = ", ".join(f"'{_esc(i)}'" for i in clean_ids)
        results = (
            table.search()
            .where(f"id IN ({escaped})", prefilter=True)
            .limit(len(clean_ids))
            .to_list()
        )
        return results

    @staticmethod
    def _normalize_iso(ts: str) -> Optional[str]:
        """Normalize a timestamp string to full ISO 8601 format.

        Handles: '2026-04-03', '2026-04-03T12:00:00Z', '2026-04-03T12:00:00+00:00'.
        Returns None if unparseable.
        """
        from datetime import datetime, timezone

        try:
            if ts.endswith("Z"):
                ts = ts[:-1] + "+00:00"
            dt = datetime.fromisoformat(ts)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat()
        except (ValueError, TypeError):
            logger.warning("_normalize_iso: cannot parse '%s'", ts)
            return None

    def query_documents(
        self,
        collection_id: Optional[str] = None,
        tags_filter: Optional[list[str]] = None,
        metadata_filter: Optional[dict] = None,
        created_after: Optional[str] = None,
        created_before: Optional[str] = None,
        content_type: Optional[str] = None,
        created_by: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """Query documents with structured filters.

        Supports filtering by:
        - collection_id: exact match
        - tags_filter: documents containing ALL specified tags
        - metadata_filter: key-value pairs matched against metadata_json
        - created_after/created_before: time range (ISO format)
        - content_type: exact match
        - created_by: exact match

        Returns list of matching documents.
        """
        table = self.get_table("documents")
        conditions: list[str] = []

        if collection_id:
            conditions.append(f"collection_id = '{_esc(collection_id)}'")
        if content_type:
            conditions.append(f"content_type = '{_esc(content_type)}'")
        if created_by:
            conditions.append(f"created_by = '{_esc(created_by)}'")
        # Normalize time range to full ISO format for correct string comparison
        if created_after:
            created_after = self._normalize_iso(created_after)
            if created_after:
                conditions.append(f"created_at >= '{_esc(created_after)}'")
        if created_before:
            created_before = self._normalize_iso(created_before)
            if created_before:
                conditions.append(f"created_at <= '{_esc(created_before)}'")

        where_clause = " AND ".join(conditions) if conditions else None
        need_post_filter = bool(tags_filter or metadata_filter)

        if not need_post_filter:
            # No post-filter: single SQL query is sufficient
            query = table.search()
            if where_clause:
                query = query.where(where_clause, prefilter=True)
            return query.limit(limit + offset).to_list()[offset:]

        # Post-filter path: fetch in batches until we have enough results
        # or exhaust the table. Prevents the 3x heuristic from silently
        # returning fewer results than requested.
        import json as _json

        target = limit + offset
        batch_size = max(target * 3, 300)  # initial batch
        max_fetch = 10000  # safety cap to avoid runaway fetches
        fetched_total = 0
        collected: list[dict] = []

        while len(collected) < target and fetched_total < max_fetch:
            query = table.search()
            if where_clause:
                query = query.where(where_clause, prefilter=True)
            # LanceDB doesn't support OFFSET natively, so we fetch progressively
            batch = query.limit(fetched_total + batch_size).to_list()
            # Only process new rows (beyond what we already processed)
            new_rows = batch[fetched_total:]
            if not new_rows:
                break  # Table exhausted

            for r in new_rows:
                # Tag filter
                if tags_filter:
                    if not all(tag in (r.get("tags") or []) for tag in tags_filter):
                        continue
                # Metadata filter
                if metadata_filter:
                    raw = r.get("metadata_json")
                    if not raw:
                        continue
                    try:
                        meta = _json.loads(raw) if isinstance(raw, str) else raw
                    except (ValueError, TypeError):
                        logger.warning(
                            "query_documents: bad metadata_json in doc %s",
                            r.get("id", "?"),
                        )
                        continue
                    if not all(meta.get(k) == v for k, v in metadata_filter.items()):
                        continue
                collected.append(r)

            fetched_total += len(new_rows)
            if len(new_rows) < batch_size:
                break  # No more rows in table
            batch_size = min(batch_size * 2, max_fetch - fetched_total)

        return collected[offset:offset + limit]

    def list_documents(
        self,
        collection_id: Optional[str] = None,
        limit: int = 100,
        tenant_id: Optional[str] = None,
    ) -> list[dict]:
        """List documents with optional collection filter."""
        table = self.get_table("documents")
        query = table.search()
        conditions: list[str] = []
        if tenant_id:
            conditions.append(f"tenant_id = '{_esc(tenant_id)}'")
        if collection_id:
            conditions.append(f"collection_id = '{_esc(collection_id)}'")
        if conditions:
            query = query.where(" AND ".join(conditions), prefilter=True)
        return query.limit(limit).to_list()

    def update_document(self, id: str, **kwargs) -> Optional[dict]:
        """Update document fields using delete-then-add pattern."""
        existing = self.get_document(id)
        if not existing:
            return None
        kwargs["updated_at"] = now_iso()
        table = self.get_table("documents")
        table.delete(f"id = '{_esc(id)}'")
        existing.update(kwargs)
        for key in list(existing.keys()):
            if key.startswith("_"):
                del existing[key]
        table.add([existing])
        return existing

    def delete_documents(self, filter_expr: str) -> bool:
        """Delete documents matching a SQL filter expression."""
        table = self.get_table("documents")
        table.delete(filter_expr)
        return True

    # ------------------------------------------------------------------
    # Relation CRUD
    # ------------------------------------------------------------------

    def create_relation(
        self,
        id: str,
        source_id: str,
        target_id: str,
        relation_type: str = "related_to",
        description: Optional[str] = None,
        confidence: float = 1.0,
        is_ai_inferred: bool = False,
        metadata_json: Optional[str] = None,
        tenant_id: str = "default",
    ) -> dict:
        """Create a new relation between two entities."""
        now = now_iso()
        relation = Relation(
            id=id,
            tenant_id=tenant_id,
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type,
            description=description,
            confidence=confidence,
            is_ai_inferred=is_ai_inferred,
            is_confirmed=False,
            metadata_json=metadata_json,
            created_at=now,
        )
        table = self.get_table("relations")
        data = relation.model_dump()
        table.add([data])
        return data

    def get_relations(
        self,
        source_id: Optional[str] = None,
        target_id: Optional[str] = None,
        relation_type: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> list[dict]:
        """Query relations with optional filters."""
        table = self.get_table("relations")
        conditions: list[str] = []
        if tenant_id:
            conditions.append(f"tenant_id = '{_esc(tenant_id)}'")
        if source_id:
            conditions.append(f"source_id = '{_esc(source_id)}'")
        if target_id:
            conditions.append(f"target_id = '{_esc(target_id)}'")
        if relation_type:
            conditions.append(f"relation_type = '{_esc(relation_type)}'")
        query = table.search()
        if conditions:
            query = query.where(" AND ".join(conditions), prefilter=True)
        return query.limit(1000).to_list()

    def delete_relation(self, id: str) -> bool:
        """Delete a single relation by ID."""
        table = self.get_table("relations")
        table.delete(f"id = '{_esc(id)}'")
        return True

    # ------------------------------------------------------------------
    # Event operations
    # ------------------------------------------------------------------

    def add_event(self, event_dict: dict, tenant_id: str = "default") -> dict:
        """Record an event to the audit log."""
        event_dict.setdefault("tenant_id", tenant_id)
        table = self.get_table("events")
        table.add([event_dict])
        return event_dict

    def add_events(self, event_dicts: list[dict], tenant_id: str = "default") -> int:
        """Record multiple events in a single batch write."""
        if not event_dicts:
            return 0
        for e in event_dicts:
            e.setdefault("tenant_id", tenant_id)
        table = self.get_table("events")
        table.add(event_dicts)
        return len(event_dicts)

    def get_events(
        self,
        target_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 50,
        tenant_id: Optional[str] = None,
    ) -> list[dict]:
        """Query events with optional filters."""
        table = self.get_table("events")
        conditions: list[str] = []
        if tenant_id:
            conditions.append(f"tenant_id = '{_esc(tenant_id)}'")
        if target_id:
            conditions.append(f"target_id = '{_esc(target_id)}'")
        if event_type:
            conditions.append(f"event_type = '{_esc(event_type)}'")
        query = table.search()
        if conditions:
            query = query.where(" AND ".join(conditions), prefilter=True)
        return query.limit(limit).to_list()

    # ------------------------------------------------------------------
    # Agent Memory
    # ------------------------------------------------------------------

    def store_memory(self, memory_dict: dict, tenant_id: str = "default") -> dict:
        """Store an agent memory entry."""
        memory_dict.setdefault("tenant_id", tenant_id)
        table = self.get_table("agent_memories")
        table.add([memory_dict])
        return memory_dict

    def get_memories(
        self,
        agent_id: str,
        memory_type: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Retrieve memories for an agent with optional type filter."""
        table = self.get_table("agent_memories")
        conditions = [f"agent_id = '{_esc(agent_id)}'"]
        if memory_type:
            conditions.append(f"memory_type = '{_esc(memory_type)}'")
        query = table.search()
        query = query.where(" AND ".join(conditions), prefilter=True)
        return query.limit(limit).to_list()

    def delete_memories(
        self,
        agent_id: str,
        memory_type: Optional[str] = None,
    ) -> bool:
        """Delete memories for an agent, optionally filtered by type."""
        table = self.get_table("agent_memories")
        if memory_type:
            table.delete(
                f"agent_id = '{_esc(agent_id)}' AND memory_type = '{_esc(memory_type)}'"
            )
        else:
            table.delete(f"agent_id = '{_esc(agent_id)}'")
        return True

    def decay_memories(
        self,
        agent_id: str,
        decay_factor: float = 0.95,
    ) -> int:
        """Decay importance of all memories for an agent.

        Memories whose importance drops below 0.01 are deleted.
        Returns count of memories affected.
        """
        memories = self.get_memories(agent_id)
        count = 0
        table = self.get_table("agent_memories")
        for mem in memories:
            old_importance = mem.get("importance", 0.5)
            new_importance = old_importance * decay_factor
            if new_importance < 0.01:
                table.delete(f"id = '{_esc(mem['id'])}'")
            else:
                table.delete(f"id = '{_esc(mem['id'])}'")
                mem["importance"] = new_importance
                for key in list(mem.keys()):
                    if key.startswith("_"):
                        del mem[key]
                table.add([mem])
            count += 1
        return count

    # ------------------------------------------------------------------
    # World Model
    # ------------------------------------------------------------------

    def get_world_model(self, tenant_id: str = "default") -> dict:
        """Get complete world model view with aggregate statistics."""
        collections = self.list_collections(tenant_id=tenant_id)

        # Count documents
        try:
            doc_table = self.get_table("documents")
            doc_count = doc_table.count_rows()
        except Exception:
            doc_count = 0

        # Count relations
        try:
            rel_table = self.get_table("relations")
            rel_count = rel_table.count_rows()
        except Exception:
            rel_count = 0

        # Count memories
        try:
            mem_table = self.get_table("agent_memories")
            mem_count = mem_table.count_rows()
        except Exception:
            mem_count = 0

        # Recent events
        events = self.get_events(limit=20)

        return WorldModel(
            collections=[
                {k: v for k, v in c.items() if not k.startswith("_")}
                for c in collections
            ],
            collection_count=len(collections),
            document_count=doc_count,
            relation_count=rel_count,
            agent_count=0,  # Would need distinct agent_id query
            memory_count=mem_count,
            recent_events=[
                {k: v for k, v in e.items() if not k.startswith("_")}
                for e in events
            ],
        ).model_dump()

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def optimize(self) -> dict:
        """Compact and clean up the database."""
        results: dict[str, dict] = {}
        for name, table in self._tables.items():
            try:
                stats = table.compact_files()
                table.cleanup_old_versions()
                results[name] = {"status": "optimized", "stats": str(stats)}
            except Exception as e:
                results[name] = {"status": "error", "error": str(e)}
        return results

    def table_stats(self) -> dict:
        """Get row counts for all tables."""
        stats: dict[str, int] = {}
        for name in [
            "collections",
            "documents",
            "relations",
            "events",
            "agent_memories",
            "universe_goals",
            "universe_deltas",
            "metrics",
            "metric_results",
        ]:
            try:
                table = self.get_table(name)
                stats[name] = table.count_rows()
            except Exception:
                stats[name] = 0
        return stats

    # ------------------------------------------------------------------
    # Universe Goal operations
    # ------------------------------------------------------------------

    def save_goal(self, goal_dict: dict, tenant_id: str = "default") -> dict:
        """Save a universe goal."""
        goal_dict.setdefault("tenant_id", tenant_id)
        table = self.get_table("universe_goals")
        table.add([goal_dict])
        return goal_dict

    def get_goal(self, goal_id: str) -> Optional[dict]:
        """Retrieve a single goal by ID."""
        table = self.get_table("universe_goals")
        results = (
            table.search()
            .where(f"id = '{_esc(goal_id)}'", prefilter=True)
            .limit(1)
            .to_list()
        )
        return results[0] if results else None

    def list_goals(
        self,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        """List goals with optional status filter."""
        table = self.get_table("universe_goals")
        query = table.search()
        if status:
            query = query.where(f"status = '{_esc(status)}'", prefilter=True)
        return query.limit(limit).to_list()

    def update_goal(self, goal_id: str, **kwargs) -> Optional[dict]:
        """Update goal fields using delete-then-add pattern."""
        existing = self.get_goal(goal_id)
        if not existing:
            return None
        kwargs["updated_at"] = now_iso()
        table = self.get_table("universe_goals")
        table.delete(f"id = '{_esc(goal_id)}'")
        existing.update(kwargs)
        for key in list(existing.keys()):
            if key.startswith("_"):
                del existing[key]
        table.add([existing])
        return existing

    # ------------------------------------------------------------------
    # Universe Delta operations
    # ------------------------------------------------------------------

    def save_delta(self, delta_dict: dict) -> dict:
        """Save a universe delta."""
        table = self.get_table("universe_deltas")
        table.add([delta_dict])
        return delta_dict

    def save_deltas(self, delta_dicts: list[dict], tenant_id: str = "default") -> int:
        """Save multiple deltas. Returns count saved."""
        if not delta_dicts:
            return 0
        for d in delta_dicts:
            d.setdefault("tenant_id", tenant_id)
        table = self.get_table("universe_deltas")
        table.add(delta_dicts)
        return len(delta_dicts)

    def get_delta(self, delta_id: str) -> Optional[dict]:
        """Retrieve a single delta by ID."""
        table = self.get_table("universe_deltas")
        results = (
            table.search()
            .where(f"id = '{_esc(delta_id)}'", prefilter=True)
            .limit(1)
            .to_list()
        )
        return results[0] if results else None

    def list_deltas(
        self,
        goal_id: Optional[str] = None,
        is_executed: Optional[bool] = None,
        limit: int = 100,
    ) -> list[dict]:
        """List deltas with optional filters."""
        table = self.get_table("universe_deltas")
        conditions: list[str] = []
        if goal_id:
            conditions.append(f"goal_id = '{_esc(goal_id)}'")
        if is_executed is not None:
            conditions.append(f"is_executed = {is_executed}")
        query = table.search()
        if conditions:
            query = query.where(" AND ".join(conditions), prefilter=True)
        return query.limit(limit).to_list()

    def update_delta(self, delta_id: str, **kwargs) -> Optional[dict]:
        """Update delta fields using delete-then-add pattern."""
        existing = self.get_delta(delta_id)
        if not existing:
            return None
        table = self.get_table("universe_deltas")
        table.delete(f"id = '{_esc(delta_id)}'")
        existing.update(kwargs)
        for key in list(existing.keys()):
            if key.startswith("_"):
                del existing[key]
        table.add([existing])
        return existing

    # ------------------------------------------------------------------
    # Metric operations
    # ------------------------------------------------------------------

    def get_metric_by_name(
        self, name: str, tenant_id: str = "default"
    ) -> Optional[dict]:
        """Find a metric by name within a tenant. Returns first match or None."""
        table = self.get_table("metrics")
        results = (
            table.search()
            .where(
                f"name = '{_esc(name)}' AND tenant_id = '{_esc(tenant_id)}'",
                prefilter=True,
            )
            .limit(1)
            .to_list()
        )
        return results[0] if results else None

    def create_metric(
        self,
        id: str,
        name: str,
        formula_json: str,
        kind: str = "scalar",
        description: Optional[str] = None,
        unit: Optional[str] = None,
        status: str = "active",
        tags: Optional[list[str]] = None,
        created_by: str = "system",
        metadata_json: Optional[str] = None,
        tenant_id: str = "default",
    ) -> dict:
        """Create a metric. Idempotent by name+tenant (returns existing)."""
        existing = self.get_metric_by_name(name, tenant_id=tenant_id)
        if existing:
            return {k: v for k, v in existing.items() if not k.startswith("_")}

        now = now_iso()
        metric = Metric(
            id=id,
            tenant_id=tenant_id,
            name=name,
            description=description,
            kind=kind,
            formula_json=formula_json,
            unit=unit,
            status=status,
            tags=tags or [],
            created_at=now,
            updated_at=now,
            created_by=created_by,
            metadata_json=metadata_json,
        )
        table = self.get_table("metrics")
        table.add([metric.model_dump()])
        return metric.model_dump()

    def get_metric(self, id: str) -> Optional[dict]:
        """Retrieve a single metric by ID."""
        table = self.get_table("metrics")
        results = (
            table.search()
            .where(f"id = '{_esc(id)}'", prefilter=True)
            .limit(1)
            .to_list()
        )
        return results[0] if results else None

    def list_metrics(
        self,
        status: Optional[str] = None,
        tenant_id: str = "default",
        limit: int = 1000,
    ) -> list[dict]:
        """List metrics with optional status filter."""
        table = self.get_table("metrics")
        conditions = [f"tenant_id = '{_esc(tenant_id)}'"]
        if status:
            conditions.append(f"status = '{_esc(status)}'")
        query = table.search().where(" AND ".join(conditions), prefilter=True)
        return query.limit(limit).to_list()

    def update_metric(self, id: str, **kwargs) -> Optional[dict]:
        """Update metric fields using delete-then-add pattern."""
        existing = self.get_metric(id)
        if not existing:
            return None
        table = self.get_table("metrics")
        table.delete(f"id = '{_esc(id)}'")
        existing.update(kwargs)
        existing["updated_at"] = now_iso()
        for key in list(existing.keys()):
            if key.startswith("_"):
                del existing[key]
        table.add([existing])
        return existing

    def delete_metric(self, id: str) -> bool:
        """Delete metric and all its results."""
        if not self.get_metric(id):
            return False
        self.get_table("metrics").delete(f"id = '{_esc(id)}'")
        # Cascade: remove all results of this metric
        try:
            self.get_table("metric_results").delete(f"metric_id = '{_esc(id)}'")
        except Exception:
            pass
        return True

    # ------------------------------------------------------------------
    # Metric result operations (time series)
    # ------------------------------------------------------------------

    def _fill_metric_result_defaults(self, r: dict, tenant_id: str) -> dict:
        """Ensure MetricResult dict has all required schema fields."""
        r.setdefault("tenant_id", tenant_id)
        r.setdefault("computed_at", now_iso())
        r.setdefault("value_numeric", 0.0)
        r.setdefault("value_json", None)
        r.setdefault("sample_count", 0)
        r.setdefault("duration_ms", 0)
        r.setdefault("error", None)
        r.setdefault("metadata_json", None)
        return r

    def save_metric_result(
        self, result_dict: dict, tenant_id: str = "default"
    ) -> dict:
        """Persist a single metric calculation result."""
        self._fill_metric_result_defaults(result_dict, tenant_id)
        table = self.get_table("metric_results")
        table.add([result_dict])
        return result_dict

    def save_metric_results(
        self, result_dicts: list[dict], tenant_id: str = "default"
    ) -> int:
        """Batch persist metric results. Returns count saved."""
        if not result_dicts:
            return 0
        for r in result_dicts:
            self._fill_metric_result_defaults(r, tenant_id)
        table = self.get_table("metric_results")
        table.add(result_dicts)
        return len(result_dicts)

    def get_metric_results(
        self,
        metric_id: str,
        limit: int = 100,
        since: Optional[str] = None,
        until: Optional[str] = None,
    ) -> list[dict]:
        """Get historical results for a metric, newest first."""
        table = self.get_table("metric_results")
        conditions = [f"metric_id = '{_esc(metric_id)}'"]
        if since:
            conditions.append(f"computed_at >= '{_esc(since)}'")
        if until:
            conditions.append(f"computed_at <= '{_esc(until)}'")
        results = (
            table.search()
            .where(" AND ".join(conditions), prefilter=True)
            .limit(limit)
            .to_list()
        )
        results.sort(key=lambda r: r.get("computed_at", ""), reverse=True)
        return results

    def get_latest_metric_result(self, metric_id: str) -> Optional[dict]:
        """Get the most recent result for a metric."""
        results = self.get_metric_results(metric_id, limit=1)
        return results[0] if results else None
