"""
Matrix 地图同步 — 从 Matrix API 拉 live 数据

配置走 config.yaml + config_loader（多环境）。

用法:
    # 用 default_env (config.yaml 里定义，通常是 test)
    MATRIX_TEST_TOKEN=xxx python3 sync.py

    # 切环境
    MATRIX_PROD_TOKEN=xxx python3 sync.py --env prod

    # 覆盖 URL（临时调试用）
    python3 sync.py --url http://localhost:8080 --token xxx

功能:
    1. 从 api_endpoints.rooms 拉房间列表 → live/rooms.json
    2. 写 live/last_sync.json (时间戳 / sha256 / 环境)
    3. 对比 rooms/*.yaml：
       - new_room: API 有 yaml 没 → 按 config.sync.stub_new_rooms 决定是否生成 stub
       - orphan:  yaml 有 API 没 → 按 config.sync.fail_on_orphan 决定是否阻断
    4. 失败退出码 ≥ 2（CI 可用）
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# 让 scripts/ 下的 import 能 work
sys.path.insert(0, str(Path(__file__).resolve().parent))
from config_loader import Config, load, print_env  # noqa: E402


def http_get(endpoint_path: str, cfg: Config) -> dict:
    url = f"{cfg.env.url}{endpoint_path}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {cfg.env.token}",
            "X-Caller-ID": cfg.env.caller_id,
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=cfg.env.timeout_sec) as resp:
        return json.loads(resp.read().decode("utf-8"))


def sync_rooms(cfg: Config) -> dict:
    endpoint = cfg.api_endpoints.get("rooms", "/api/admin/rooms")
    try:
        data = http_get(endpoint, cfg)
    except urllib.error.HTTPError as e:
        print(f"[ERROR] {endpoint} HTTP {e.code}: {e.reason}", file=sys.stderr)
        sys.exit(2)
    except urllib.error.URLError as e:
        print(f"[ERROR] {endpoint} 无法到达: {e}", file=sys.stderr)
        sys.exit(2)

    rooms = data.get("rooms", [])
    live_dir = cfg.root / "live"
    live_dir.mkdir(parents=True, exist_ok=True)

    out_path = live_dir / "rooms.json"
    raw = json.dumps(rooms, ensure_ascii=False, indent=2, sort_keys=True)
    out_path.write_text(raw, encoding="utf-8")

    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    sync_meta = {
        "env": cfg.env.name,
        "source_url": f"{cfg.env.url}{endpoint}",
        "synced_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "room_count": len(rooms),
        "sha256": digest,
        "caller_id": cfg.env.caller_id,
    }
    (live_dir / "last_sync.json").write_text(
        json.dumps(sync_meta, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    return {"rooms": rooms, "meta": sync_meta}


def detect_drift(rooms: list[dict], cfg: Config) -> tuple[list[str], list[str]]:
    """对比 rooms/*.yaml 和 live。返回 (new_rooms, orphans)."""
    import yaml as _yaml

    live_keys = {r["room_key"] for r in rooms}
    rooms_dir = cfg.root / "rooms"
    rooms_dir.mkdir(parents=True, exist_ok=True)

    yaml_keys: dict[str, Path] = {}
    for p in rooms_dir.glob("*.yaml"):
        try:
            data = _yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            key = data.get("room_key")
            if key:
                yaml_keys[key] = p
        except Exception as e:
            print(f"[WARN] 无法解析 {p.name}: {e}", file=sys.stderr)

    new_rooms = sorted(live_keys - set(yaml_keys.keys()))
    orphans = sorted(k for k in yaml_keys if k not in live_keys)
    return new_rooms, orphans


def stub_new_room(room: dict, cfg: Config) -> Path:
    key = room["room_key"]
    path = cfg.root / "rooms" / f"{key}.yaml"
    if path.exists():
        return path

    now = time.strftime("%Y-%m-%d")
    stub = f"""# 自动生成 stub (env={cfg.env.name}) — 请填 operations 后 commit
id: room-{key}
title: TODO 中文名
kind: room
parent: TODO area-id
room_key: {key}
room_version: {room.get('version', 'TODO')}
accepted_task_types: {json.dumps(room.get('accepted_task_types', []), ensure_ascii=False)}
summary: TODO 30-60 字说明
source: api
verified_at: {now}
verified_by: sync.py
stale_days: 14

# 每个 operation 必须有 1-3 个 docs
operations: []
"""
    path.write_text(stub, encoding="utf-8")
    return path


def main():
    ap = argparse.ArgumentParser(description="Matrix 地图同步")
    ap.add_argument("--env", help="环境 (test/prod/local)，覆盖 default_env")
    ap.add_argument("--url", help="直接覆盖 URL")
    ap.add_argument("--token", help="直接覆盖 token（不推荐，用 env）")
    ap.add_argument("--caller", help="覆盖 X-Caller-ID")
    ap.add_argument("--dry-run", action="store_true", help="不写文件，仅打印")
    args = ap.parse_args()

    cfg = load(
        env_name=args.env,
        url_override=args.url,
        token_override=args.token,
        caller_override=args.caller,
    )
    print_env(cfg)

    if args.dry_run:
        print("[dry-run] 跳过实际拉取与写盘")
        return

    result = sync_rooms(cfg)
    meta = result["meta"]
    print(f"  room_count: {meta['room_count']}")
    print(f"  sha256:     {meta['sha256']}")
    print(f"  synced_at:  {meta['synced_at']}")

    new_rooms, orphans = detect_drift(result["rooms"], cfg)

    if new_rooms:
        print(f"\n[NEW] API 有 / yaml 没 ({len(new_rooms)})：")
        if cfg.sync.get("stub_new_rooms", True):
            for k in new_rooms:
                room = next(r for r in result["rooms"] if r["room_key"] == k)
                stub_path = stub_new_room(room, cfg)
                print(f"  + {k}  → stub: {stub_path.relative_to(cfg.root)}")
        else:
            for k in new_rooms:
                print(f"  + {k}  (未生成 stub，config.sync.stub_new_rooms=false)")

    if orphans:
        print(f"\n[ORPHAN] yaml 有 / API 没 ({len(orphans)})：")
        for k in orphans:
            print(f"  - {k}")
        if cfg.sync.get("fail_on_orphan", False):
            print("\n[FAIL] config.sync.fail_on_orphan=true，退出", file=sys.stderr)
            sys.exit(2)

    if not new_rooms and not orphans:
        print("\n✓ 无 drift，地图与 live 对齐")


if __name__ == "__main__":
    main()
