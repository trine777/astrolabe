#!/usr/bin/env python3
"""
从老 xingtu SQLite 迁移到 Astrolabe LanceDB

映射：
  meta_objects    → Collection (name 幂等，file_path/row_count 放 metadata)
  meta_properties → Document   (一列一个文档，sample_values/data_type 放 metadata)
  meta_relations  → Relation   (source_object_id → target_object_id，relation_type 映射)
  metric_defs     → Metric     (formula 是自然语言/SQL → 写占位 formula_json + legacy_formula)

用法:
  python scripts/migrate_from_xingtu.py --source <old.db> [--tenant default] [--dry-run]

环境变量:
  XINGTU_DB_PATH         Astrolabe LanceDB 目录
  XINGTU_EMBEDDING_PROVIDER  推荐 'none' 以避免每列都跑 embedding
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import uuid
from pathlib import Path
from typing import Dict, List

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from xingtu import XingTuService  # noqa: E402
from xingtu.config import XingTuConfig  # noqa: E402

# Old xingtu relation_type → Astrolabe RelationType
RELATION_MAP = {
    "oneToOne": "related_to",
    "oneToMany": "related_to",
    "manyToOne": "related_to",
    "manyToMany": "related_to",
    "references": "references",
    "derived_from": "derived_from",
    "part_of": "part_of",
    "contains": "contains",
}


def load_sqlite(path: str) -> sqlite3.Connection:
    if not Path(path).exists():
        raise FileNotFoundError(f"Source DB not found: {path}")
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def migrate_objects(
    conn: sqlite3.Connection,
    service: XingTuService,
    tenant_id: str,
    dry_run: bool,
) -> Dict[str, str]:
    """Object → Collection. Returns {old_object_id: new_collection_id}"""
    mapping: Dict[str, str] = {}
    rows = conn.execute("SELECT * FROM meta_objects").fetchall()
    for row in rows:
        d = dict(row)
        name = d.get("name") or d.get("original_name") or f"obj-{d['id'][:8]}"
        tags = []
        raw_tags = d.get("tags")
        if raw_tags:
            try:
                tags = json.loads(raw_tags) if isinstance(raw_tags, str) else list(raw_tags)
            except Exception:
                tags = []

        meta = {
            "legacy_id": d["id"],
            "object_type": d.get("object_type"),
            "file_path": d.get("file_path"),
            "row_count": d.get("row_count"),
            "status": d.get("status"),
        }

        if dry_run:
            print(f"  [dry] Collection: {name} ({len(tags)} tags)")
            mapping[d["id"]] = f"dry-col-{d['id'][:8]}"
            continue

        col = service.create_collection(
            name=name,
            description=d.get("description"),
            collection_type="structured",
            tags=tags,
            metadata_json=json.dumps(meta, ensure_ascii=False),
            created_by="migration",
            tenant_id=tenant_id,
        )
        mapping[d["id"]] = col["id"]
        print(f"  Collection: {name} → {col['id'][:8]}")

    return mapping


def migrate_properties(
    conn: sqlite3.Connection,
    service: XingTuService,
    obj_mapping: Dict[str, str],
    tenant_id: str,
    dry_run: bool,
) -> Dict[str, str]:
    """Property → Document (batched per collection). Returns {old_property_id: new_doc_id}"""
    mapping: Dict[str, str] = {}
    rows = conn.execute("SELECT * FROM meta_properties").fetchall()

    # Group by object
    by_object: Dict[str, List[dict]] = {}
    for row in rows:
        d = dict(row)
        old_obj = d["object_id"]
        by_object.setdefault(old_obj, []).append(d)

    from xingtu.models import now_iso

    for old_obj, props in by_object.items():
        col_id = obj_mapping.get(old_obj)
        if not col_id:
            print(f"  SKIP properties of unmapped object: {old_obj}")
            continue

        docs = []
        for p in props:
            doc_id = str(uuid.uuid4())
            mapping[p["id"]] = doc_id
            meta = {
                "legacy_id": p["id"],
                "legacy_object_id": old_obj,
                "original_name": p.get("original_name"),
                "data_type": p.get("data_type"),
                "semantic_type": p.get("semantic_type"),
                "unit": p.get("unit"),
                "null_count": p.get("null_count"),
                "unique_count": p.get("unique_count"),
                "sample_values": p.get("sample_values"),
            }
            content = p.get("display_name") or p.get("original_name") or "(unnamed column)"
            if p.get("description"):
                content = f"{content}: {p['description']}"
            now = now_iso()
            docs.append(
                {
                    "id": doc_id,
                    "collection_id": col_id,
                    "content": content,
                    "content_type": "text",
                    "tags": ["property"],
                    "metadata_json": json.dumps(meta, ensure_ascii=False),
                    "created_at": now,
                    "updated_at": now,
                    "created_by": "migration",
                }
            )

        if dry_run:
            print(f"  [dry] Documents: {len(docs)} for collection {col_id[:8]}")
            continue

        service.store.add_documents(docs, tenant_id=tenant_id)
        print(f"  Documents: {len(docs)} → collection {col_id[:8]}")

    return mapping


def migrate_relations(
    conn: sqlite3.Connection,
    service: XingTuService,
    id_mapping: Dict[str, str],
    tenant_id: str,
    dry_run: bool,
) -> int:
    """Relation → Relation. Maps source/target object IDs via mapping."""
    rows = conn.execute("SELECT * FROM meta_relations").fetchall()
    count = 0
    for row in rows:
        d = dict(row)
        src = id_mapping.get(d["source_object_id"])
        tgt = id_mapping.get(d["target_object_id"])
        if not src or not tgt:
            print(f"  SKIP relation (missing endpoint): {d['source_object_id']} → {d['target_object_id']}")
            continue

        rel_type = RELATION_MAP.get(d.get("relation_type"), "related_to")
        confidence = d.get("confidence") or 1.0
        is_ai = bool(d.get("is_ai_inferred") or 0)

        if dry_run:
            print(f"  [dry] Relation: {src[:8]} --[{rel_type}]--> {tgt[:8]}")
            count += 1
            continue

        service.store.create_relation(
            id=str(uuid.uuid4()),
            source_id=src,
            target_id=tgt,
            relation_type=rel_type,
            description=d.get("description"),
            confidence=float(confidence),
            is_ai_inferred=is_ai,
        )
        count += 1
    return count


def migrate_metrics(
    conn: sqlite3.Connection,
    service: XingTuService,
    obj_mapping: Dict[str, str],
    tenant_id: str,
    dry_run: bool,
) -> List[dict]:
    """
    MetricDef → Metric. formula 是老系统的自然语言/SQL，不能直接执行。
    写入占位 formula_json (count source_collections[0])，原始 formula 保留到 metadata.legacy_formula。
    返回需要人工处理的指标列表。
    """
    rows = conn.execute("SELECT * FROM metric_defs").fetchall()
    needs_manual: List[dict] = []

    for row in rows:
        d = dict(row)
        name = d.get("name") or d.get("display_name") or f"metric-{d['id'][:8]}"

        # Parse source_object_ids
        raw_sources = d.get("source_object_ids") or "[]"
        try:
            sources = json.loads(raw_sources) if isinstance(raw_sources, str) else list(raw_sources)
        except Exception:
            sources = []

        # Resolve first source to collection_id if possible
        source_col = None
        for s in sources:
            if s in obj_mapping:
                source_col = obj_mapping[s]
                break
        # Fallback: if sources is a list of names (not IDs), try to look up later
        if not source_col and sources:
            # Use the raw name — migration script caller will see this as a warning
            source_col = sources[0] if isinstance(sources[0], str) else "UNMAPPED_SOURCE"

        placeholder_formula = {
            "op": "count",
            "source": source_col or "UNMAPPED",
            "comment": "auto-generated placeholder; translate legacy_formula into DSL",
        }

        meta = {
            "legacy_id": d["id"],
            "legacy_formula": d.get("formula"),
            "legacy_source_object_ids": sources,
            "dimensions": d.get("dimensions"),
            "aggregation_type": d.get("aggregation_type"),
            "display_name": d.get("display_name"),
        }

        if dry_run:
            print(f"  [dry] Metric: {name} (placeholder formula)")
            needs_manual.append({"name": name, "legacy_formula": d.get("formula")})
            continue

        try:
            service.create_metric(
                name=name,
                formula=placeholder_formula,
                kind="scalar",
                description=d.get("description"),
                unit=d.get("unit"),
                tags=["migrated", "needs-manual-formula"],
                metadata_json=json.dumps(meta, ensure_ascii=False),
                created_by="migration",
                tenant_id=tenant_id,
            )
            print(f"  Metric: {name} (placeholder, legacy formula preserved)")
            needs_manual.append({"name": name, "legacy_formula": d.get("formula")})
        except Exception as e:
            print(f"  FAIL metric {name}: {e}")

    return needs_manual


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, help="Old xingtu SQLite path")
    ap.add_argument("--tenant", default="default", help="Astrolabe tenant_id")
    ap.add_argument("--dry-run", action="store_true", help="Show what would be migrated without writing")
    args = ap.parse_args()

    conn = load_sqlite(args.source)

    print(f"=== Migrating from {args.source} to Astrolabe ===")
    print(f"  Tenant: {args.tenant}")
    print(f"  Mode: {'DRY-RUN' if args.dry_run else 'EXECUTE'}")
    print()

    if args.dry_run:
        # Minimal service for dry-run validation
        service = None
    else:
        os.environ.setdefault("XINGTU_EMBEDDING_PROVIDER", "none")
        config = XingTuConfig.from_env()
        service = XingTuService(config)
        service.initialize()

    # Handle dry-run with proxy service
    class DryRunService:
        def create_collection(self, **kwargs):
            return {"id": f"dry-col-{uuid.uuid4().hex[:8]}", **kwargs}

        class _Store:
            def add_documents(self, docs, tenant_id="default"):
                return len(docs)

            def create_relation(self, **kwargs):
                pass

        store = _Store()

        def create_metric(self, **kwargs):
            return {"id": f"dry-metric-{uuid.uuid4().hex[:8]}", **kwargs}

    svc = service if service else DryRunService()

    print("--- Step 1: Objects → Collections ---")
    obj_mapping = migrate_objects(conn, svc, args.tenant, args.dry_run)
    print(f"  Migrated {len(obj_mapping)} objects")
    print()

    print("--- Step 2: Properties → Documents ---")
    prop_mapping = migrate_properties(conn, svc, obj_mapping, args.tenant, args.dry_run)
    print(f"  Migrated {len(prop_mapping)} properties")
    print()

    print("--- Step 3: Relations ---")
    # Combine mapping: relations use object IDs (not property IDs) in this schema
    rel_count = migrate_relations(conn, svc, obj_mapping, args.tenant, args.dry_run)
    print(f"  Migrated {rel_count} relations")
    print()

    print("--- Step 4: Metrics (placeholders) ---")
    needs_manual = migrate_metrics(conn, svc, obj_mapping, args.tenant, args.dry_run)
    print(f"  Migrated {len(needs_manual)} metrics")
    print()

    print("=== Summary ===")
    print(f"  Collections: {len(obj_mapping)}")
    print(f"  Documents:   {len(prop_mapping)}")
    print(f"  Relations:   {rel_count}")
    print(f"  Metrics:     {len(needs_manual)}")
    if needs_manual:
        print()
        print("  Metrics needing manual formula translation:")
        for m in needs_manual:
            legacy = (m.get("legacy_formula") or "")[:80]
            print(f"    - {m['name']}: {legacy!r}")


if __name__ == "__main__":
    main()
