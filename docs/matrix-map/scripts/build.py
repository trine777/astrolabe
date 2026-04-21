"""
地图合并构建 — 把 areas/ + rooms/ + live/ 合并成单文件 MATRIX_OPS_MAP.yaml

输出给 agent 一次加载用。会：
  1. 读所有 areas/*.yaml → L1 节点
  2. 读所有 rooms/*.yaml → L2 节点（含 operations）
  3. 读 live/rooms.json → 补充 room 的 api-side 字段（version/status/accepted_task_types）
  4. 按 parent 关系组装成树
  5. 写 MATRIX_OPS_MAP.yaml + MATRIX_OPS_MAP.sha256
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config_loader import Config, load, print_env  # noqa: E402


def load_yaml_dir(base: Path) -> list[dict]:
    if not base.exists():
        return []
    out = []
    for p in sorted(base.glob("*.yaml")):
        try:
            data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            if isinstance(data, dict):
                out.append(data)
        except yaml.YAMLError as e:
            print(f"[WARN] {p.name}: {e}", file=sys.stderr)
    return out


def enrich_rooms_from_live(rooms: list[dict], cfg: Config) -> None:
    """把 live 数据合并进 room 节点（原地修改）。"""
    live_file = cfg.root / "live" / "rooms.json"
    if not live_file.exists():
        return
    try:
        live_rooms = json.loads(live_file.read_text(encoding="utf-8"))
    except Exception:
        return
    live_by_key = {r["room_key"]: r for r in live_rooms}
    for room in rooms:
        key = room.get("room_key")
        if key and key in live_by_key:
            live = live_by_key[key]
            room.setdefault("live", {})
            room["live"] = {
                "room_definition_id": live.get("room_definition_id"),
                "version": live.get("version"),
                "status": live.get("status"),
                "accepted_task_types": live.get("accepted_task_types", []),
                "registered_at": live.get("registered_at"),
            }


def assemble_tree(areas: list[dict], rooms: list[dict]) -> dict:
    """把 area 和 room 组装成 {area: {rooms: [{room, operations: [...]}]}}."""
    areas_by_id = {a["id"]: dict(a, rooms=[]) for a in areas if a.get("id")}

    for room in rooms:
        parent = room.get("parent")
        target = areas_by_id.get(parent)
        if target:
            target["rooms"].append(room)
        else:
            areas_by_id.setdefault(
                "__orphan__",
                {"id": "__orphan__", "title": "未归类（parent 不存在）", "kind": "area", "rooms": []},
            )["rooms"].append(room)

    return {
        "schema_version": "1",
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "areas": list(areas_by_id.values()),
    }


def main():
    ap = argparse.ArgumentParser(description="Matrix 地图构建")
    ap.add_argument("--env", help="环境（影响 live 合并来源）")
    ap.add_argument("--output", default="MATRIX_OPS_MAP.yaml", help="输出文件名")
    args = ap.parse_args()

    cfg = load(env_name=args.env, require_token=False)
    print_env(cfg)

    areas = load_yaml_dir(cfg.root / "areas")
    rooms = load_yaml_dir(cfg.root / "rooms")

    enrich_rooms_from_live(rooms, cfg)
    tree = assemble_tree(areas, rooms)
    tree["env"] = cfg.env.name

    out_path = cfg.root / args.output
    raw = yaml.safe_dump(tree, allow_unicode=True, sort_keys=False, default_flow_style=False)
    out_path.write_text(raw, encoding="utf-8")

    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    (cfg.root / f"{args.output}.sha256").write_text(digest, encoding="utf-8")

    area_cnt = len(tree["areas"])
    room_cnt = sum(len(a.get("rooms", [])) for a in tree["areas"])
    op_cnt = sum(
        len(r.get("operations", []) or [])
        for a in tree["areas"] for r in a.get("rooms", [])
    )
    doc_cnt = sum(
        len((op.get("docs") or []))
        for a in tree["areas"] for r in a.get("rooms", [])
        for op in (r.get("operations") or [])
    )

    print(f"✓ 已生成 {out_path.relative_to(cfg.root)}  sha256={digest}")
    print(f"  areas={area_cnt}  rooms={room_cnt}  operations={op_cnt}  docs={doc_cnt}")
    size_kb = len(raw) / 1024
    print(f"  size={size_kb:.1f} KB")


if __name__ == "__main__":
    main()
