"""
地图合并构建 — 把 areas/ + rooms/ + live/ 合并成单文件 MATRIX_OPS_MAP.yaml

输出给 agent 一次加载用。会：
  1. 读所有 areas/*.yaml → L1 节点
  2. 读所有 rooms/*.yaml → L2 节点（含 operations）
  3. 读 live/rooms.json → 补充 room 的 api-side 字段
  4. 检查 live 新鲜度（E1）
  5. 检查 orphan room（E2，默认阻断）
  6. 按 parent 关系组装成树
  7. 写 MATRIX_OPS_MAP.yaml + MATRIX_OPS_MAP.sha256
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import date, datetime, timezone
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


def _parse_version(v) -> int:
    try:
        return int(v)
    except (ValueError, TypeError):
        return -1


def load_live_rooms(cfg: Config) -> dict[str, dict]:
    """D1: 从 live/rooms.json 读，按 room_key 去重取最高 version。"""
    live_file = cfg.root / "live" / "rooms.json"
    if not live_file.exists():
        return {}
    try:
        rooms = json.loads(live_file.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[WARN] live/rooms.json 解析失败: {e}", file=sys.stderr)
        return {}

    by_key: dict[str, dict] = {}
    for r in rooms:
        k = r.get("room_key")
        if not k:
            continue
        if k not in by_key:
            by_key[k] = r
        else:
            prev_v = _parse_version(by_key[k].get("version"))
            cur_v = _parse_version(r.get("version"))
            if cur_v > prev_v:
                by_key[k] = r
    return by_key


def check_live_freshness(cfg: Config) -> list[str]:
    """E1: live 数据过期返回错误列表。"""
    errors = []
    last_path = cfg.root / "live" / "last_sync.json"
    if not last_path.exists():
        errors.append("缺少 live/last_sync.json — 请先 make sync")
        return errors

    try:
        meta = json.loads(last_path.read_text(encoding="utf-8"))
    except Exception as e:
        errors.append(f"live/last_sync.json 解析失败: {e}")
        return errors

    # env 一致性
    synced_env = meta.get("env")
    if synced_env and synced_env != cfg.env.name:
        errors.append(
            f"live 数据来自 env={synced_env}，当前构建 env={cfg.env.name}。"
            f"先 make sync ENV={cfg.env.name}"
        )

    # 时效性
    synced_at_str = meta.get("synced_at", "")
    stale_days = int(cfg.validate.get("live_stale_days", 7))
    if synced_at_str:
        try:
            # "2026-04-21T14:29:42Z"
            synced_dt = datetime.strptime(synced_at_str[:19], "%Y-%m-%dT%H:%M:%S")
            synced_dt = synced_dt.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            age_days = (now - synced_dt).days
            if age_days > stale_days:
                errors.append(
                    f"live 数据已 {age_days} 天未刷新（阈值 {stale_days}）。"
                    f"先 make sync"
                )
        except ValueError:
            errors.append(f"synced_at 格式无法解析: {synced_at_str!r}")

    return errors


def enrich_rooms_from_live(rooms: list[dict], live_by_key: dict[str, dict]) -> None:
    """把 live 数据合并进 room 节点（原地修改）。"""
    for room in rooms:
        key = room.get("room_key")
        if key and key in live_by_key:
            live = live_by_key[key]
            room["live"] = {
                "room_definition_id": live.get("room_definition_id"),
                "version": live.get("version"),
                "status": live.get("status"),
                "accepted_task_types": live.get("accepted_task_types", []),
                "registered_at": live.get("registered_at"),
            }


def assemble_tree(
    areas: list[dict],
    rooms: list[dict],
    cfg: Config,
) -> tuple[dict, list[str]]:
    """组装树，返回 (tree, orphan_errors)."""
    errors: list[str] = []
    areas_by_id = {a["id"]: dict(a, rooms=[]) for a in areas if a.get("id")}

    orphans: list[str] = []
    for room in rooms:
        parent = room.get("parent")
        target = areas_by_id.get(parent) if parent else None
        if target:
            target["rooms"].append(room)
        else:
            orphans.append(
                f"room '{room.get('id', '?')}' (key={room.get('room_key', '?')}) "
                f"parent='{parent or '<空>'}' 未对应任何 area"
            )

    # E2: orphan 默认阻断
    if orphans:
        if cfg.build.get("fail_on_orphan", True):
            errors.extend(f"orphan room: {o}" for o in orphans)
        else:
            # 降级：放兜底 area 里但打 warning（config 明确关掉才走这里）
            fake = {
                "id": "__orphan__",
                "title": "未归类 — 请人工归区",
                "kind": "area",
                "rooms": [],
            }
            for room in rooms:
                parent = room.get("parent")
                if parent not in areas_by_id:
                    fake["rooms"].append(room)
            areas_by_id["__orphan__"] = fake

    tree = {
        "schema_version": "1",
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "env": cfg.env.name,
        "areas": list(areas_by_id.values()),
    }
    return tree, errors


def main():
    ap = argparse.ArgumentParser(description="Matrix 地图构建")
    ap.add_argument("--env", help="环境（影响 live 合并来源）")
    ap.add_argument("--output", default="MATRIX_OPS_MAP.yaml", help="输出文件名")
    ap.add_argument("--dry-run", action="store_true", help="不写盘，只检查")
    ap.add_argument("--skip-live-check", action="store_true", help="跳过 live 时效检查")
    args = ap.parse_args()

    cfg = load(env_name=args.env, require_token=False)
    print_env(cfg)

    # E1: live 时效性 + env 一致性
    fresh_errors: list[str] = []
    if not args.skip_live_check:
        fresh_errors = check_live_freshness(cfg)
        if fresh_errors and cfg.build.get("fail_on_stale_live", True):
            for e in fresh_errors:
                print(f"[ERROR] {e}", file=sys.stderr)
            print("\n✗ live 数据检查失败，--skip-live-check 可临时绕过", file=sys.stderr)
            sys.exit(1)
        for e in fresh_errors:
            print(f"[WARN] {e}", file=sys.stderr)

    areas = load_yaml_dir(cfg.root / "areas")
    rooms = load_yaml_dir(cfg.root / "rooms")
    live_by_key = load_live_rooms(cfg)

    enrich_rooms_from_live(rooms, live_by_key)
    tree, orphan_errors = assemble_tree(areas, rooms, cfg)

    if orphan_errors:
        for e in orphan_errors:
            print(f"[ERROR] {e}", file=sys.stderr)
        print("\n✗ 发现 orphan room，build 阻断", file=sys.stderr)
        print("   如是测试调试，可 build.fail_on_orphan: false", file=sys.stderr)
        sys.exit(1)

    raw = yaml.safe_dump(tree, allow_unicode=True, sort_keys=False, default_flow_style=False)

    if args.dry_run:
        print("[dry-run] 跳过写盘")
    else:
        out_path = cfg.root / args.output
        out_path.write_text(raw, encoding="utf-8")
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
        (cfg.root / f"{args.output}.sha256").write_text(digest, encoding="utf-8")
        print(f"✓ 已生成 {out_path.relative_to(cfg.root)}  sha256={digest}")

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
    print(f"  areas={area_cnt}  rooms={room_cnt}  operations={op_cnt}  docs={doc_cnt}")
    size_kb = len(raw) / 1024
    print(f"  size={size_kb:.1f} KB")


if __name__ == "__main__":
    main()
