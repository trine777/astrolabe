"""
Matrix 地图校验 — 根据 schema.yaml 全量校验 areas/ 和 rooms/

退出码:
    0  全部通过
    1  有 error
    2  有 warning（当 config.validate.strict=true 时按 error 处理）

校验项:
    E1  id 全局唯一
    E2  parent 引用的 id 必须存在
    E3  kind 合法 (area/room/operation)
    E4  operation 节点 docs 数 1-3
    E5  必填字段齐全 (按 kind)
    E6  room_key 必须在 live/rooms.json 中 (除非 skip_live_check)
    E7  doc.type 合法 + 必填 title/content
    W1  verified_at 过期 (> stale_days)
    W2  live/rooms.json 有但 rooms/ 下无 (orphan room)
    W3  type=curl 的 doc content 未含 "curl" 或 "-X"
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config_loader import Config, load, print_env  # noqa: E402


ALLOWED_KINDS = {"area", "room", "operation"}
ALLOWED_DOC_TYPES = {"curl", "rule", "checklist", "diagram", "payload"}


def _is_placeholder(val) -> bool:
    """V1: 识别 TODO / 空串 / None 等占位符，真阻断。"""
    if val is None:
        return True
    s = str(val).strip()
    if not s:
        return True
    if s.upper().startswith("TODO") or s == "__TODO__":
        return True
    return False


def load_all_nodes(cfg: Config) -> tuple[list[dict], list[tuple[str, str]]]:
    """扫 areas/ 和 rooms/ 下所有 yaml，提取节点。返回 (nodes, parse_errors)."""
    nodes: list[dict] = []
    errs: list[tuple[str, str]] = []

    for sub in ("areas", "rooms"):
        base = cfg.root / sub
        if not base.exists():
            continue
        for p in sorted(base.glob("*.yaml")):
            try:
                data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError as e:
                errs.append((str(p.relative_to(cfg.root)), f"YAML 解析失败: {e}"))
                continue
            if not isinstance(data, dict):
                errs.append((str(p.relative_to(cfg.root)), "根不是 object"))
                continue
            data["_source_file"] = str(p.relative_to(cfg.root))
            nodes.append(data)

            # 展开 operations 作为独立节点
            for op in data.get("operations", []) or []:
                if not isinstance(op, dict):
                    errs.append((str(p.relative_to(cfg.root)), f"operations 子项非 object: {op}"))
                    continue
                op_copy = dict(op)
                op_copy.setdefault("kind", "operation")
                op_copy.setdefault("parent", data.get("id"))
                op_copy["_source_file"] = str(p.relative_to(cfg.root))
                nodes.append(op_copy)

    return nodes, errs


def load_live_room_keys(cfg: Config) -> set[str]:
    live_file = cfg.root / "live" / "rooms.json"
    if not live_file.exists():
        return set()
    try:
        data = json.loads(live_file.read_text(encoding="utf-8"))
        return {r["room_key"] for r in data if isinstance(r, dict) and "room_key" in r}
    except Exception:
        return set()


def parse_date(s: str) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def validate_nodes(nodes: list[dict], live_keys: set[str], cfg: Config):
    errors: list[str] = []
    warnings: list[str] = []

    # E1 id 全局唯一
    seen_ids: dict[str, str] = {}
    for n in nodes:
        nid = n.get("id")
        if not nid:
            errors.append(f"[E5] 缺 id: {n.get('_source_file', '?')}")
            continue
        if nid in seen_ids:
            errors.append(
                f"[E1] id 重复 '{nid}' at {n.get('_source_file')}, 先出现于 {seen_ids[nid]}"
            )
        else:
            seen_ids[nid] = n.get("_source_file", "?")

    all_ids = set(seen_ids.keys())

    # W2 orphan room (live 有 / rooms 没)
    if not cfg.validate.get("skip_live_check", False):
        covered_keys = {n.get("room_key") for n in nodes if n.get("kind") == "room"}
        orphan_live = live_keys - covered_keys
        for k in orphan_live:
            warnings.append(f"[W2] live 有 room '{k}' 但 rooms/ 下没对应 yaml")

    stale_days_default = int(cfg.validate.get("stale_days_default", 14))
    today = date.today()

    # W5: live 数据过期
    live_stale_days = int(cfg.validate.get("live_stale_days", 7))
    last_sync_path = cfg.root / "live" / "last_sync.json"
    if last_sync_path.exists():
        try:
            last = json.loads(last_sync_path.read_text(encoding="utf-8"))
            synced_at = last.get("synced_at", "")
            if synced_at:
                # 格式 "2026-04-21T14:29:42Z"
                synced_date = datetime.strptime(synced_at[:10], "%Y-%m-%d").date()
                age = (today - synced_date).days
                if age > live_stale_days:
                    warnings.append(
                        f"[W5] live 数据已 {age} 天未刷新（阈值 {live_stale_days}），"
                        f"建议先 make sync"
                    )
        except Exception:
            pass

    # 按父 id 分组，给 V2/V3 用
    children_by_parent: dict[str, list[dict]] = {}
    for n in nodes:
        p = n.get("parent")
        if p:
            children_by_parent.setdefault(p, []).append(n)

    for n in nodes:
        src = n.get("_source_file", "?")
        nid = n.get("id", "?")
        kind = n.get("kind")

        # E3 kind 合法
        if kind not in ALLOWED_KINDS:
            errors.append(f"[E3] {nid}: kind='{kind}' 非法，允许 {ALLOWED_KINDS}")
            continue

        # E5 必填字段（V1: TODO/空串都当缺失）
        for fld in ("title", "verified_at"):
            if _is_placeholder(n.get(fld)):
                errors.append(f"[E5] {nid} ({src}): 字段 '{fld}' 为空/占位符")

        # E2 parent 引用（V1: TODO/空串 → E5, 否则查引用）
        parent = n.get("parent")
        if kind in ("room", "operation"):
            if _is_placeholder(parent):
                errors.append(f"[E5] {nid}: kind={kind} 必须有 parent（当前为空/占位符）")
            elif parent not in all_ids:
                errors.append(f"[E2] {nid}: parent='{parent}' 不存在")

        # E6 room_key 必须在 live（虚拟 room 豁免，如 __platform__）
        if kind == "room":
            rk = n.get("room_key")
            if not rk:
                errors.append(f"[E5] {nid}: room 节点必须有 room_key")
            elif rk.startswith("__") and rk.endswith("__"):
                # 虚拟 room (__platform__ 等): 装跨 room 的通用 op, 不对应 Matrix 真实 room
                pass
            elif not cfg.validate.get("skip_live_check", False):
                if rk not in live_keys:
                    errors.append(f"[E6] {nid}: room_key '{rk}' 不在 live/rooms.json")

        # E4 operation docs 数 1-3
        if kind == "operation":
            docs = n.get("docs") or []
            if not isinstance(docs, list):
                errors.append(f"[E4] {nid}: docs 必须是 list")
            elif not (1 <= len(docs) <= 3):
                errors.append(f"[E4] {nid}: docs 数 {len(docs)}，应 1-3")
            else:
                for i, d in enumerate(docs):
                    if not isinstance(d, dict):
                        errors.append(f"[E7] {nid}.docs[{i}]: 非 object")
                        continue
                    if d.get("type") not in ALLOWED_DOC_TYPES:
                        errors.append(
                            f"[E7] {nid}.docs[{i}]: type='{d.get('type')}' 非法，"
                            f"允许 {ALLOWED_DOC_TYPES}"
                        )
                    if not d.get("title"):
                        errors.append(f"[E7] {nid}.docs[{i}]: 缺 title")
                    if not d.get("content"):
                        errors.append(f"[E7] {nid}.docs[{i}]: 缺 content")
                    # W3 curl shape
                    if d.get("type") == "curl":
                        content = str(d.get("content", ""))
                        if ("curl" not in content) and ("-X" not in content):
                            warnings.append(
                                f"[W3] {nid}.docs[{i}]: curl 未见 'curl' 或 '-X'"
                            )

        # V2/V3: area/room 必须有子节点
        if kind == "area":
            kids = children_by_parent.get(nid, [])
            if not any(c.get("kind") == "room" for c in kids):
                warnings.append(f"[W4] area '{nid}': 无任何 room 子节点")
        elif kind == "room":
            kids = children_by_parent.get(nid, [])
            # operations 可能在同一 yaml 里内联，也可能是独立节点
            has_op = any(c.get("kind") == "operation" for c in kids)
            if not has_op:
                warnings.append(f"[W4] room '{nid}': 无任何 operation 子节点")

        # W1 verified_at 过期
        verified = parse_date(n.get("verified_at"))
        if verified:
            stale_days = int(n.get("stale_days", stale_days_default))
            age_days = (today - verified).days
            if age_days > stale_days:
                warnings.append(
                    f"[W1] {nid}: verified_at={verified} 已过期 {age_days}/{stale_days} 天"
                )

    return errors, warnings


def main():
    ap = argparse.ArgumentParser(description="Matrix 地图校验")
    ap.add_argument("--env", help="环境（影响 live 对比来源）")
    ap.add_argument("--strict", action="store_true", help="warning 按 error 处理")
    ap.add_argument("--skip-live-check", action="store_true", help="跳过 live 对比")
    args = ap.parse_args()

    cfg = load(env_name=args.env, require_token=False)
    if args.strict:
        cfg.validate["strict"] = True
    if args.skip_live_check:
        cfg.validate["skip_live_check"] = True

    print_env(cfg)

    nodes, parse_errs = load_all_nodes(cfg)
    live_keys = load_live_room_keys(cfg)

    print(f"  节点: {len(nodes)}  (areas: {sum(1 for n in nodes if n.get('kind')=='area')}, "
          f"rooms: {sum(1 for n in nodes if n.get('kind')=='room')}, "
          f"operations: {sum(1 for n in nodes if n.get('kind')=='operation')})")
    print(f"  live rooms: {len(live_keys)}")
    print()

    errors = []
    warnings = []

    for f, msg in parse_errs:
        errors.append(f"[PARSE] {f}: {msg}")

    e, w = validate_nodes(nodes, live_keys, cfg)
    errors.extend(e)
    warnings.extend(w)

    if errors:
        print(f"[ERROR] {len(errors)} 条：")
        for m in errors:
            print(f"  {m}")
    if warnings:
        print(f"\n[WARN] {len(warnings)} 条：")
        for m in warnings:
            print(f"  {m}")

    strict = cfg.validate.get("strict", False)
    if errors or (strict and warnings):
        print(f"\n✗ 校验失败 ({'strict' if strict else 'normal'})")
        sys.exit(1)

    if warnings:
        print(f"\n△ 有 {len(warnings)} 条 warning，但 non-strict 放行")
        sys.exit(0)

    print("✓ 全部通过")


if __name__ == "__main__":
    main()
