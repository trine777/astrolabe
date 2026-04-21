"""
Matrix 地图同步 — 从 Matrix API 拉 live 数据

配置走 config.yaml + config_loader（多环境）。

用法:
    # 用 default_env (config.yaml 里定义，通常是 prod)
    MATRIX_PROD_TOKEN=xxx python3 sync.py

    # 切环境
    MATRIX_TEST_TOKEN=xxx python3 sync.py --env test

    # 推荐：token 写文件，避免 shell history 泄漏
    echo $MATRIX_PROD_TOKEN > ~/.matrix-token && chmod 600 ~/.matrix-token
    python3 sync.py --token-file ~/.matrix-token

功能:
    1. 从 api_endpoints.rooms 拉房间列表 → live/rooms.json (去重同 room_key)
    2. 写 live/last_sync.json (时间戳 / sha256 / 环境)
    3. 检测 env 一致性：上次 sync 用 test，这次用 prod 要先警告
    4. 对比 rooms/*.yaml：
       - new_room: API 有 yaml 没 → 按 config.sync.stub_new_rooms 决定是否生成 stub
       - orphan:  yaml 有 API 没 → 按 config.sync.fail_on_orphan 决定是否阻断
    5. 失败退出码 ≥ 2（CI 可用）
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


def _parse_version(v) -> int:
    """尽量把 version 转成可比较整数；解析失败返回 -1。"""
    try:
        return int(v)
    except (ValueError, TypeError):
        return -1


def dedup_rooms(rooms: list[dict]) -> tuple[list[dict], list[dict]]:
    """D1: 按 room_key 去重，保留 version 最高一条。返回 (uniq, conflicts)."""
    by_key: dict[str, dict] = {}
    conflicts: list[dict] = []
    for r in rooms:
        key = r.get("room_key")
        if not key:
            continue
        if key not in by_key:
            by_key[key] = r
            continue
        prev = by_key[key]
        prev_v = _parse_version(prev.get("version"))
        cur_v = _parse_version(r.get("version"))
        conflicts.append({
            "room_key": key,
            "kept_version": max(prev_v, cur_v),
            "dropped_version": min(prev_v, cur_v),
            "kept_room_definition_id": (r if cur_v > prev_v else prev).get("room_definition_id"),
            "dropped_room_definition_id": (prev if cur_v > prev_v else r).get("room_definition_id"),
        })
        if cur_v > prev_v:
            by_key[key] = r
    uniq = sorted(by_key.values(), key=lambda r: r.get("room_key", ""))
    return uniq, conflicts


def check_env_consistency(cfg: Config) -> None:
    """C3: 如上次 sync 是别的 env，警告要求清理或确认。"""
    last_path = cfg.root / "live" / "last_sync.json"
    if not last_path.exists():
        return
    try:
        last = json.loads(last_path.read_text(encoding="utf-8"))
    except Exception:
        return
    last_env = last.get("env")
    if last_env and last_env != cfg.env.name:
        print(
            f"[WARN] 上次 sync 使用 env={last_env}，本次是 env={cfg.env.name}。"
            f"\n       继续会覆盖 live/ 下的数据。如需保留请先 make clean 或切回 {last_env}。",
            file=sys.stderr,
        )


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

    raw_rooms = data.get("rooms", [])

    # D1: 去重
    rooms, conflicts = dedup_rooms(raw_rooms)
    if conflicts:
        print(f"[WARN] live 返回 {len(conflicts)} 组同 room_key 重复，按 version 去重:", file=sys.stderr)
        for c in conflicts:
            print(
                f"       - {c['room_key']}: 保留 v{c['kept_version']} "
                f"({c['kept_room_definition_id']}), 丢弃 v{c['dropped_version']} "
                f"({c['dropped_room_definition_id']})",
                file=sys.stderr,
            )

    live_dir = cfg.root / "live"
    live_dir.mkdir(parents=True, exist_ok=True)

    out_path = live_dir / "rooms.json"
    raw = json.dumps(rooms, ensure_ascii=False, indent=2, sort_keys=True)
    out_path.write_text(raw, encoding="utf-8")

    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    sync_meta = {
        "env": cfg.env.name,
        "source_url": f"{cfg.env.url}{endpoint}",   # 只含 host+path，不带 query
        "synced_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "room_count": len(rooms),
        "raw_room_count": len(raw_rooms),
        "dedup_conflicts": len(conflicts),
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
        except (_yaml.YAMLError, OSError) as e:
            print(f"[WARN] 无法解析 {p.name}: {e}", file=sys.stderr)
            continue
        # D2: kind=room 但无 room_key → 字段名可能写错
        if isinstance(data, dict):
            if data.get("kind") == "room" and not data.get("room_key"):
                print(
                    f"[WARN] {p.name}: kind=room 但无 room_key 字段，可能字段名写错",
                    file=sys.stderr,
                )
            key = data.get("room_key")
            if key:
                yaml_keys[key] = p

    new_rooms = sorted(live_keys - set(yaml_keys.keys()))
    orphans = sorted(k for k in yaml_keys if k not in live_keys)
    return new_rooms, orphans


def stub_new_room(room: dict, cfg: Config) -> Path:
    """D3: stub 的 title/parent 用空串而非 'TODO xxx'，让 validate 能真阻断。"""
    key = room["room_key"]
    path = cfg.root / "rooms" / f"{key}.yaml"
    if path.exists():
        return path

    now = time.strftime("%Y-%m-%d")
    accepted = json.dumps(room.get("accepted_task_types", []), ensure_ascii=False)
    stub = f"""# 自动生成 stub (env={cfg.env.name}) — 必须填 title / parent / operations 才能过校验
id: room-{key}
title: ""                                  # TODO: 填中文名
kind: room
parent: ""                                 # TODO: 填 area id
room_key: {key}
room_version: {room.get('version', '')}
accepted_task_types: {accepted}
summary: ""                                # TODO: 30-60 字
source: api
synced_at: {now}                           # 机器填的同步时间
verified_at: ""                            # TODO: 人工验证后填 YYYY-MM-DD
verified_by: ""
stale_days: 14

# operations: 每个必须有 1-3 个 docs
operations: []
"""
    path.write_text(stub, encoding="utf-8")
    return path


def _read_token_file(path: str) -> str:
    """S3: 从文件读 token，避免 CLI 泄漏。"""
    p = Path(path).expanduser()
    if not p.exists():
        print(f"[ERROR] token file 不存在: {p}", file=sys.stderr)
        sys.exit(3)
    # 检查权限
    mode = p.stat().st_mode & 0o777
    if mode & 0o077:
        print(
            f"[WARN] {p} 权限 {oct(mode)} 过宽，建议 chmod 600",
            file=sys.stderr,
        )
    return p.read_text(encoding="utf-8").strip()


def main():
    ap = argparse.ArgumentParser(description="Matrix 地图同步")
    ap.add_argument("--env", help="环境 (test/prod/local)，覆盖 default_env")
    ap.add_argument("--url", help="直接覆盖 URL")
    ap.add_argument("--token", help="(不推荐) 直接覆盖 token；会进 shell history")
    ap.add_argument("--token-file", help="从文件读 token (推荐)")
    ap.add_argument("--caller", help="覆盖 X-Caller-ID")
    ap.add_argument("--dry-run", action="store_true", help="不写文件，仅打印")
    args = ap.parse_args()

    token_override = None
    if args.token_file:
        token_override = _read_token_file(args.token_file)
    elif args.token:
        print(
            "[WARN] --token 明文会进 shell history / CI 日志，建议改用 --token-file 或 env var",
            file=sys.stderr,
        )
        token_override = args.token

    cfg = load(
        env_name=args.env,
        url_override=args.url,
        token_override=token_override,
        caller_override=args.caller,
    )
    print_env(cfg)

    # C3: 检测 env 不一致
    check_env_consistency(cfg)

    if args.dry_run:
        print("[dry-run] 跳过实际拉取与写盘")
        return

    result = sync_rooms(cfg)
    meta = result["meta"]
    print(f"  room_count: {meta['room_count']}  (raw={meta['raw_room_count']}, dedup_conflicts={meta['dedup_conflicts']})")
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
