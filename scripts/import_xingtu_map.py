"""
把 docs/xingtu-map/ 下的 yaml 导入星图自述地图 (areas + organs + operations).

和 import_matrix_map.py 区别: 这里 L2 节点是 organ 不是 room.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

MAP_DIR = ROOT / "docs" / "xingtu-map"
AREAS_DIR = MAP_DIR / "areas"
ORGANS_DIR = MAP_DIR / "organs"


def load_yaml_files(base: Path) -> list[dict]:
    if not base.exists():
        return []
    out = []
    for p in sorted(base.glob("*.yaml")):
        try:
            data = yaml.safe_load(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                out.append(data)
        except yaml.YAMLError as e:
            print(f"[WARN] 跳过 {p.name}: {e}", file=sys.stderr)
    return out


def collect():
    areas_yaml = load_yaml_files(AREAS_DIR)
    organs_yaml = load_yaml_files(ORGANS_DIR)

    areas = [
        {
            "id": a["id"],
            "title": a["title"],
            "summary": a.get("summary", ""),
            "tags": a.get("tags", []),
            "metadata": {"source": a.get("source", "human")},
        }
        for a in areas_yaml
    ]

    organs = []
    operations = []
    for o in organs_yaml:
        organs.append({
            "id": o["id"],
            "parent_area_id": o["parent"],
            "title": o["title"],
            "summary": o.get("summary", ""),
            "module_path": o.get("module_path"),
            "tags": o.get("tags", []),
            "extra_metadata": {
                "source": o.get("source", "human"),
                "verified_at": o.get("verified_at", ""),
            },
        })
        for op in o.get("operations", []) or []:
            operations.append({
                "id": op["id"],
                "parent_room_id": op["parent"],   # service 参数叫 parent_room_id 但接 organ 也行
                "title": op["title"],
                "docs": [
                    {
                        "type": d["type"],
                        "title": d["title"],
                        "content": d["content"],
                        "language": d.get("language"),
                    }
                    for d in op.get("docs", []) or []
                ],
                "summary": op.get("summary", ""),
                "tags": op.get("tags", []),
                "verified_at": op.get("verified_at", ""),
                "verified_by": op.get("verified_by", ""),
                "source": op.get("source", "human"),
                "references": op.get("references", []),
            })

    return areas, organs, operations


def main():
    ap = argparse.ArgumentParser(description="导入 xingtu-map 到星图 LanceDB")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    areas, organs, operations = collect()
    print(f"扫描: {MAP_DIR}")
    print(f"  areas: {len(areas)}  organs: {len(organs)}  operations: {len(operations)}")
    if args.dry_run:
        return

    from xingtu import XingTuService
    svc = XingTuService(); svc.initialize()
    mm = svc.matrix_map

    counts = {"areas": 0, "organs": 0, "operations": 0, "errors": []}

    for a in areas:
        try:
            mm.register_area(
                area_id=a["id"], title=a["title"], summary=a["summary"],
                tags=a.get("tags"), metadata=a.get("metadata"),
            )
            counts["areas"] += 1
        except Exception as e:
            counts["errors"].append(f"area {a['id']}: {e}")

    for o in organs:
        try:
            mm.register_organ(
                organ_id=o["id"], parent_area_id=o["parent_area_id"], title=o["title"],
                summary=o["summary"], module_path=o.get("module_path"),
                tags=o.get("tags"), extra_metadata=o.get("extra_metadata"),
            )
            counts["organs"] += 1
        except Exception as e:
            counts["errors"].append(f"organ {o['id']}: {e}")

    for op in operations:
        try:
            mm.register_operation(
                operation_id=op["id"], parent_room_id=op["parent_room_id"],
                title=op["title"], docs=op["docs"], summary=op.get("summary", ""),
                tags=op.get("tags"), verified_at=op.get("verified_at", ""),
                verified_by=op.get("verified_by", ""), source=op.get("source", "human"),
                references=op.get("references"),
            )
            counts["operations"] += 1
        except Exception as e:
            counts["errors"].append(f"operation {op['id']}: {e}")

    ov = mm.overview()
    print()
    print("=== 注册结果 ===")
    print(f"  areas:      {counts['areas']}")
    print(f"  organs:     {counts['organs']}")
    print(f"  operations: {counts['operations']}")
    if counts["errors"]:
        print(f"  errors ({len(counts['errors'])}):")
        for e in counts["errors"]:
            print(f"    - {e}")
    print()
    print("=== 星图内 overview (含 Matrix 地图 + 本 xingtu 自述地图) ===")
    print(f"  area_count: {ov['area_count']}")
    print(f"  room_count: {ov['room_count']} (Matrix rooms)")
    print(f"  organ_count: {ov.get('organ_count', 0)} (xingtu organs)")
    print(f"  operation_count: {ov['operation_count']}")


if __name__ == "__main__":
    main()
