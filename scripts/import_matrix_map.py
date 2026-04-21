"""
把 docs/matrix-map/ 下的 yaml 导入星图 LanceDB。

两种模式:
  1. 直连 (默认): 直接 import service, 在本进程里注册
  2. HTTP (--via-http): 调用 Astrolabe API /api/v1/matrix-map/bulk-register

用法:
    # 本地直连（最简单，无需 API server 运行）
    python3 scripts/import_matrix_map.py

    # 走 HTTP API
    python3 scripts/import_matrix_map.py \\
        --via-http http://localhost:8000 \\
        --tenant default

输出: 注册数 / 错误 / 最终 overview
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

# 允许从 project root 或 scripts/ 下跑
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


MAP_DIR = ROOT / "docs" / "matrix-map"
AREAS_DIR = MAP_DIR / "areas"
ROOMS_DIR = MAP_DIR / "rooms"


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


def collect_areas_and_rooms() -> tuple[list[dict], list[dict], list[dict]]:
    """从 yaml 抽取 area / room / operation 三个列表。"""
    areas_yaml = load_yaml_files(AREAS_DIR)
    rooms_yaml = load_yaml_files(ROOMS_DIR)

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

    rooms = []
    operations = []
    for r in rooms_yaml:
        rooms.append({
            "id": r["id"],
            "parent_area_id": r["parent"],
            "title": r["title"],
            "room_key": r["room_key"],
            "summary": r.get("summary", ""),
            "accepted_task_types": r.get("accepted_task_types", []),
            "tags": r.get("tags", []),
            "extra_metadata": {
                "room_version": r.get("room_version"),
                "source": r.get("source", "human"),
                "verified_at": r.get("verified_at", ""),
            },
        })
        for op in r.get("operations", []) or []:
            operations.append({
                "id": op["id"],
                "parent_room_id": op["parent"],
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

    return areas, rooms, operations


def register_direct(areas: list[dict], rooms: list[dict], operations: list[dict]) -> dict:
    """直连 XingTuService 注册（不走 HTTP）。"""
    from xingtu import XingTuService

    svc = XingTuService()
    svc.initialize()
    mm = svc.matrix_map

    counts = {"areas": 0, "rooms": 0, "operations": 0, "errors": []}

    for a in areas:
        try:
            mm.register_area(
                area_id=a["id"], title=a["title"], summary=a["summary"],
                tags=a.get("tags"), metadata=a.get("metadata"),
            )
            counts["areas"] += 1
        except Exception as e:
            counts["errors"].append(f"area {a['id']}: {e}")

    for r in rooms:
        try:
            mm.register_room(
                room_id=r["id"], parent_area_id=r["parent_area_id"],
                title=r["title"], room_key=r["room_key"],
                summary=r["summary"],
                accepted_task_types=r.get("accepted_task_types"),
                tags=r.get("tags"), extra_metadata=r.get("extra_metadata"),
            )
            counts["rooms"] += 1
        except Exception as e:
            counts["errors"].append(f"room {r['id']}: {e}")

    for o in operations:
        try:
            mm.register_operation(
                operation_id=o["id"], parent_room_id=o["parent_room_id"],
                title=o["title"], docs=o["docs"], summary=o.get("summary", ""),
                tags=o.get("tags"), verified_at=o.get("verified_at", ""),
                verified_by=o.get("verified_by", ""), source=o.get("source", "human"),
                references=o.get("references"),
            )
            counts["operations"] += 1
        except Exception as e:
            counts["errors"].append(f"operation {o['id']}: {e}")

    return counts, mm.overview()


def register_via_http(
    areas: list[dict], rooms: list[dict], operations: list[dict],
    url: str, tenant: str,
) -> tuple[dict, dict]:
    import urllib.request

    def post(path: str, body: dict) -> dict:
        req = urllib.request.Request(
            f"{url.rstrip('/')}{path}",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-Tenant-ID": tenant},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))

    def get(path: str) -> dict:
        req = urllib.request.Request(f"{url.rstrip('/')}{path}")
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))

    result = post(
        "/api/v1/matrix-map/bulk-register",
        {"areas": areas, "rooms": rooms, "operations": operations},
    )
    overview = get("/api/v1/matrix-map/overview")
    return result, overview


def main():
    ap = argparse.ArgumentParser(description="把 yaml 地图导入星图")
    ap.add_argument("--via-http", help="走 Astrolabe API HTTP 导入（如 http://localhost:8000）")
    ap.add_argument("--tenant", default="default", help="租户 ID")
    args = ap.parse_args()

    print(f"扫描: {MAP_DIR}")
    areas, rooms, operations = collect_areas_and_rooms()
    print(f"  areas: {len(areas)}  rooms: {len(rooms)}  operations: {len(operations)}")

    if args.via_http:
        print(f"走 HTTP: {args.via_http}  tenant={args.tenant}")
        counts, overview = register_via_http(areas, rooms, operations, args.via_http, args.tenant)
    else:
        print("直连 XingTuService")
        counts, overview = register_direct(areas, rooms, operations)

    print()
    print("=== 注册结果 ===")
    print(f"  areas:      {counts['areas']}")
    print(f"  rooms:      {counts['rooms']}")
    print(f"  operations: {counts['operations']}")
    if counts.get("errors"):
        print(f"  errors ({len(counts['errors'])}):")
        for e in counts["errors"]:
            print(f"    - {e}")

    print()
    print("=== 星图内 overview ===")
    print(f"  area_count: {overview['area_count']}")
    print(f"  room_count: {overview['room_count']}")
    print(f"  operation_count: {overview['operation_count']}")
    for a in overview.get("areas", []):
        print(f"  - {a['id']:20s} rooms={a['room_count']}  ops={a['operation_count']}")


if __name__ == "__main__":
    main()
