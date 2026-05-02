"""星图 XingTu - 可观测性指标计算

L3 价值层 + L2 体验层 + L1 容量层 共 17 个指标.

数据源: events 表 (event_type 命名空间隔离, after_snapshot 存 JSON metadata).
spec: docs/metrics/EVENT_SCHEMA.md

无数据时所有函数返回 rate=0.0, samples=0, 不抛错 — 适合冷启动期.
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from .store import XingkongzuoStore

logger = logging.getLogger(__name__)

# events.get_events 默认 limit=50, 指标需要全量. 各函数按窗口大小选 limit.
_LIMIT_HIGH = 100_000
_EPOCH = datetime.min.replace(tzinfo=timezone.utc)


# ============================================================
# 工具
# ============================================================


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def _parse_meta(event: dict) -> dict:
    raw = event.get("after_snapshot")
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    if len(s) == 1:
        return float(s[0])
    k = (len(s) - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return float(s[f])
    return float(s[f] + (s[c] - s[f]) * (k - f))


def _events_since(
    store: "XingkongzuoStore",
    event_type: str,
    since: datetime,
    limit: int = _LIMIT_HIGH,
) -> list[dict]:
    raw = store.get_events(event_type=event_type, limit=limit)
    out = []
    for e in raw:
        ts = _parse_iso(e.get("timestamp"))
        if ts and ts >= since:
            out.append(e)
    return out


def _user_id(event: dict, meta: Optional[dict] = None) -> Optional[str]:
    if meta is None:
        meta = _parse_meta(event)
    return meta.get("user_id") or event.get("actor_id")


# ============================================================
# L3 价值层 (4 项)
# ============================================================


def w12_completion_rate(
    store: "XingkongzuoStore",
    cohort_month: Optional[str] = None,
) -> dict:
    """M-3.1: W12 完成率 (按月队列, 84d 内拿到 W12 报告占启动用户)."""
    started = store.get_events(event_type="fyd.session_started", limit=_LIMIT_HIGH)
    reports = store.get_events(event_type="fyd.report_generated", limit=_LIMIT_HIGH)

    user_started: dict[str, datetime] = {}
    for e in started:
        meta = _parse_meta(e)
        uid = _user_id(e, meta)
        ts = _parse_iso(e.get("timestamp"))
        if not uid or not ts:
            continue
        if uid not in user_started or ts < user_started[uid]:
            user_started[uid] = ts

    user_w12: dict[str, datetime] = {}
    for e in reports:
        meta = _parse_meta(e)
        if meta.get("week_number") != 12:
            continue
        uid = _user_id(e, meta)
        ts = _parse_iso(e.get("timestamp"))
        if not uid or not ts:
            continue
        if uid not in user_w12 or ts < user_w12[uid]:
            user_w12[uid] = ts

    by_cohort: dict[str, list[tuple[datetime, Optional[datetime]]]] = defaultdict(list)
    for uid, st in user_started.items():
        by_cohort[st.strftime("%Y-%m")].append((st, user_w12.get(uid)))

    now = _now()
    mature_cutoff = now - timedelta(days=84)

    if cohort_month:
        target = cohort_month
    else:
        mature = [
            cm for cm, rows in by_cohort.items()
            if any(st <= mature_cutoff for st, _ in rows)
        ]
        target = max(mature) if mature else None

    if not target or target not in by_cohort:
        return {
            "metric": "w12_completion_rate",
            "cohort_month": target,
            "started": 0,
            "completed": 0,
            "rate": 0.0,
            "mature": False,
        }

    rows = by_cohort[target]
    total = len(rows)
    completed = sum(
        1 for st, w12 in rows
        if w12 is not None and (w12 - st) <= timedelta(days=84)
    )
    return {
        "metric": "w12_completion_rate",
        "cohort_month": target,
        "started": total,
        "completed": completed,
        "rate": completed / total if total else 0.0,
        "mature": all(st <= mature_cutoff for st, _ in rows),
    }


def _w4_active_set(store: "XingkongzuoStore") -> tuple[set[str], set[str]]:
    """返回 (eligible_started_users, w4_active_users) — 复用给 M-3.2/3.4."""
    started = store.get_events(event_type="fyd.session_started", limit=_LIMIT_HIGH)
    completed = store.get_events(event_type="fyd.session_completed", limit=_LIMIT_HIGH)

    cutoff = _now() - timedelta(days=35)
    user_started: dict[str, datetime] = {}
    for e in started:
        meta = _parse_meta(e)
        uid = _user_id(e, meta)
        ts = _parse_iso(e.get("timestamp"))
        if not uid or not ts:
            continue
        if uid not in user_started or ts < user_started[uid]:
            user_started[uid] = ts

    eligible = {uid for uid, st in user_started.items() if st <= cutoff}

    active: set[str] = set()
    for e in completed:
        meta = _parse_meta(e)
        if meta.get("week_number", 0) >= 4:
            uid = _user_id(e, meta)
            if uid in eligible:
                active.add(uid)
    return eligible, active


def w4_retention_rate(store: "XingkongzuoStore") -> dict:
    """M-3.2: W4 留存率 (按议会序号, 不按日历)."""
    eligible, active = _w4_active_set(store)
    return {
        "metric": "w4_retention_rate",
        "started": len(eligible),
        "active_w4": len(active),
        "rate": len(active) / len(eligible) if eligible else 0.0,
    }


def resolution_adoption_rate(
    store: "XingkongzuoStore",
    days: int = 30,
    collection_name: str = "fyd_resolutions",
) -> dict:
    """M-3.3: 决议采纳率 (documents 表 metadata.adoption_status='adopted')."""
    cutoff_iso = (_now() - timedelta(days=days)).isoformat()

    coll = store.get_collection_by_name(collection_name)
    if not coll:
        return {
            "metric": "resolution_adoption_rate",
            "window_days": days,
            "total": 0,
            "adopted": 0,
            "rate": 0.0,
            "note": f"collection '{collection_name}' not found",
        }

    table = store.get_table("documents")
    try:
        rows = (
            table.search()
            .where(f"collection_id = '{coll['id']}'", prefilter=True)
            .limit(_LIMIT_HIGH)
            .to_list()
        )
    except Exception as ex:
        logger.warning(f"resolution_adoption_rate query failed: {ex}")
        rows = []

    recent = [r for r in rows if r.get("created_at", "") >= cutoff_iso]
    adopted = 0
    for r in recent:
        try:
            meta = json.loads(r.get("metadata_json") or "{}")
        except Exception:
            meta = {}
        if meta.get("adoption_status") == "adopted":
            adopted += 1

    return {
        "metric": "resolution_adoption_rate",
        "window_days": days,
        "total": len(recent),
        "adopted": adopted,
        "rate": adopted / len(recent) if recent else 0.0,
    }


def paid_conversion_rate(store: "XingkongzuoStore") -> dict:
    """M-3.4: W4 active 中持有有效订阅的比例."""
    paid = store.get_events(event_type="fyd.subscription_paid", limit=_LIMIT_HIGH)
    canceled = store.get_events(event_type="fyd.subscription_canceled", limit=_LIMIT_HIGH)

    user_last_paid: dict[str, datetime] = {}
    for e in paid:
        meta = _parse_meta(e)
        if meta.get("plan") == "trial":
            continue
        uid = _user_id(e, meta)
        ts = _parse_iso(e.get("timestamp"))
        if not uid or not ts:
            continue
        if ts > user_last_paid.get(uid, _EPOCH):
            user_last_paid[uid] = ts

    user_last_canceled: dict[str, datetime] = {}
    for e in canceled:
        meta = _parse_meta(e)
        uid = _user_id(e, meta)
        ts = _parse_iso(e.get("timestamp"))
        if not uid or not ts:
            continue
        if ts > user_last_canceled.get(uid, _EPOCH):
            user_last_canceled[uid] = ts

    paid_now = {
        uid for uid, p in user_last_paid.items()
        if p > user_last_canceled.get(uid, _EPOCH)
    }

    _, w4_active = _w4_active_set(store)
    overlap = w4_active & paid_now
    return {
        "metric": "paid_conversion_rate",
        "w4_active": len(w4_active),
        "paid": len(overlap),
        "rate": len(overlap) / len(w4_active) if w4_active else 0.0,
    }


# ============================================================
# L2 体验层 (5 项)
# ============================================================


def session_quality_rate(
    store: "XingkongzuoStore",
    days: int = 7,
    threshold: int = 4,
) -> dict:
    """M-2.1: 议会发言质量 (≥threshold 占比)."""
    since = _now() - timedelta(days=days)
    events = _events_since(store, "fyd.session_scored", since)

    scores: list[float] = []
    for e in events:
        meta = _parse_meta(e)
        s = meta.get("score")
        if isinstance(s, (int, float)):
            scores.append(float(s))

    high = sum(1 for s in scores if s >= threshold)
    return {
        "metric": "session_quality_rate",
        "window_days": days,
        "threshold": threshold,
        "scored": len(scores),
        "high_quality": high,
        "rate": high / len(scores) if scores else 0.0,
    }


def session_success_rate(store: "XingkongzuoStore", hours: int = 24) -> dict:
    """M-2.2: 议会成功率 (用户主动取消从分母剔除)."""
    since = _now() - timedelta(hours=hours)

    started = _events_since(store, "fyd.session_started", since)
    completed = _events_since(store, "fyd.session_completed", since)
    failed = _events_since(store, "fyd.session_failed", since)

    started_ids: set[str] = {e["target_id"] for e in started if e.get("target_id")}

    user_canceled = 0
    for e in failed:
        meta = _parse_meta(e)
        if meta.get("cancel_reason") == "user_cancel":
            sid = e.get("target_id")
            if sid in started_ids:
                started_ids.discard(sid)
                user_canceled += 1

    completed_ids = {
        e["target_id"] for e in completed
        if e.get("target_id") in started_ids
    }
    return {
        "metric": "session_success_rate",
        "window_hours": hours,
        "started": len(started_ids),
        "completed": len(completed_ids),
        "user_canceled": user_canceled,
        "rate": len(completed_ids) / len(started_ids) if started_ids else 0.0,
    }


def report_generation_p95(
    store: "XingkongzuoStore",
    hours: int = 24,
    timeout_seconds: float = 600.0,
) -> dict:
    """M-2.3: 报告生成 p95 (session_completed → report_generated)."""
    since = _now() - timedelta(hours=hours)
    completed = _events_since(store, "fyd.session_completed", since)
    reports = _events_since(store, "fyd.report_generated", since)

    sess_completed: dict[str, datetime] = {}
    for e in completed:
        sid = e.get("target_id")
        ts = _parse_iso(e.get("timestamp"))
        if sid and ts:
            sess_completed[sid] = ts

    sess_report: dict[str, datetime] = {}
    for e in reports:
        sid = e.get("target_id")
        ts = _parse_iso(e.get("timestamp"))
        if sid and ts:
            sess_report[sid] = ts

    durations: list[float] = []
    for sid, c_ts in sess_completed.items():
        r_ts = sess_report.get(sid)
        durations.append(
            (r_ts - c_ts).total_seconds() if r_ts else timeout_seconds
        )

    return {
        "metric": "report_generation_p95",
        "window_hours": hours,
        "samples": len(durations),
        "p50_seconds": _percentile(durations, 50),
        "p95_seconds": _percentile(durations, 95),
    }


def api_error_rate(store: "XingkongzuoStore", minutes: int = 5) -> dict:
    """M-2.4: API 5xx 占总请求比例 (4xx 不计 — 用户错)."""
    since = _now() - timedelta(minutes=minutes)
    events = _events_since(store, "api.request", since)

    total = 0
    err = 0
    for e in events:
        meta = _parse_meta(e)
        status = meta.get("status")
        if not isinstance(status, int):
            continue
        total += 1
        if status >= 500:
            err += 1
    return {
        "metric": "api_error_rate",
        "window_minutes": minutes,
        "total": total,
        "errors_5xx": err,
        "rate": err / total if total else 0.0,
    }


def search_hit_rate(
    store: "XingkongzuoStore",
    days: int = 7,
    top_n: int = 3,
    click_window_seconds: float = 30.0,
) -> dict:
    """M-2.5: 搜索后 30s 内点击 top-N 的比例."""
    since = _now() - timedelta(days=days)
    searches = _events_since(store, "fyd.search_performed", since)
    clicks = _events_since(store, "fyd.search_clicked", since)

    search_ts: dict[str, datetime] = {}
    for e in searches:
        sid = e.get("target_id")
        ts = _parse_iso(e.get("timestamp"))
        if sid and ts:
            search_ts[sid] = ts

    hits: set[str] = set()
    for e in clicks:
        sid = e.get("target_id")
        ts = _parse_iso(e.get("timestamp"))
        meta = _parse_meta(e)
        rank = meta.get("rank", 999)
        if not (sid and ts and isinstance(rank, int)):
            continue
        if sid in search_ts and rank <= top_n:
            if (ts - search_ts[sid]).total_seconds() <= click_window_seconds:
                hits.add(sid)

    return {
        "metric": "search_hit_rate",
        "window_days": days,
        "top_n": top_n,
        "searches": len(search_ts),
        "hits": len(hits),
        "rate": len(hits) / len(search_ts) if search_ts else 0.0,
    }


# ============================================================
# L1 容量层 (8 项)
# ============================================================


_READ_ROUTES_PREFIX = ("GET /api/v1/search", "GET /api/v1/collections", "GET /api/v1/documents")
_WRITE_METHODS = ("POST", "PUT", "PATCH", "DELETE")


def _api_latency_p95(
    store: "XingkongzuoStore",
    minutes: int,
    metric_name: str,
    is_read: bool,
) -> dict:
    since = _now() - timedelta(minutes=minutes)
    events = _events_since(store, "api.request", since)

    latencies: list[float] = []
    for e in events:
        meta = _parse_meta(e)
        route = meta.get("route", "")
        method = meta.get("method", "")
        status = meta.get("status", 0)
        latency = meta.get("latency_ms")

        if not isinstance(latency, (int, float)):
            continue
        # 4xx 排除 (用户错请求不计性能容量)
        if isinstance(status, int) and 400 <= status < 500:
            continue
        if not route.startswith("/api/v1/"):
            continue

        key = f"{method} {route}"
        matches_read = method == "GET" and any(key.startswith(p) for p in _READ_ROUTES_PREFIX)
        matches_write = method in _WRITE_METHODS

        if (is_read and matches_read) or (not is_read and matches_write):
            latencies.append(float(latency))

    return {
        "metric": metric_name,
        "window_minutes": minutes,
        "samples": len(latencies),
        "p50_ms": _percentile(latencies, 50),
        "p95_ms": _percentile(latencies, 95),
    }


def api_read_p95(store: "XingkongzuoStore", minutes: int = 5) -> dict:
    """M-1.1: API read p95 latency (search/get docs)."""
    return _api_latency_p95(store, minutes, "api_read_p95", is_read=True)


def api_write_p95(store: "XingkongzuoStore", minutes: int = 5) -> dict:
    """M-1.2: API write p95 latency (POST/PUT/PATCH/DELETE)."""
    return _api_latency_p95(store, minutes, "api_write_p95", is_read=False)


def _internal_p95(
    store: "XingkongzuoStore",
    event_type: str,
    metric_name: str,
    minutes: int,
) -> dict:
    since = _now() - timedelta(minutes=minutes)
    events = _events_since(store, event_type, since)
    latencies = [
        float(m["latency_ms"]) for m in (_parse_meta(e) for e in events)
        if isinstance(m.get("latency_ms"), (int, float))
    ]
    return {
        "metric": metric_name,
        "window_minutes": minutes,
        "samples": len(latencies),
        "p50_ms": _percentile(latencies, 50),
        "p95_ms": _percentile(latencies, 95),
    }


def embedding_p95(store: "XingkongzuoStore", minutes: int = 5) -> dict:
    """M-1.3: Embedding 调用 p95."""
    return _internal_p95(store, "internal.embed", "embedding_p95", minutes)


def lancedb_query_p95(store: "XingkongzuoStore", minutes: int = 5) -> dict:
    """M-1.4: LanceDB 查询 p95."""
    return _internal_p95(store, "internal.lancedb_query", "lancedb_query_p95", minutes)


def disk_usage(store: "XingkongzuoStore", lookback_hours: int = 2) -> dict:
    """M-1.5: 磁盘占用 (取最近一次 internal.disk_check)."""
    since = _now() - timedelta(hours=lookback_hours)
    events = _events_since(store, "internal.disk_check", since)
    if not events:
        return {
            "metric": "disk_usage",
            "samples": 0,
            "used_bytes": 0,
            "total_bytes": 0,
            "ratio": 0.0,
        }

    latest = max(events, key=lambda e: _parse_iso(e.get("timestamp")) or _EPOCH)
    meta = _parse_meta(latest)
    used = int(meta.get("used_bytes", 0))
    total = int(meta.get("total_bytes", 0))
    return {
        "metric": "disk_usage",
        "samples": len(events),
        "used_bytes": used,
        "total_bytes": total,
        "ratio": used / total if total else 0.0,
    }


def embedding_provider_uptime(store: "XingkongzuoStore", hours: int = 1) -> dict:
    """M-1.6: Embedding provider 可用率 (按 provider 拆)."""
    since = _now() - timedelta(hours=hours)
    events = _events_since(store, "internal.embed_ping", since)

    by_provider: dict[str, dict[str, int]] = defaultdict(lambda: {"ok": 0, "total": 0})
    for e in events:
        meta = _parse_meta(e)
        provider = meta.get("provider", "unknown")
        by_provider[provider]["total"] += 1
        if meta.get("status") == "ok":
            by_provider[provider]["ok"] += 1

    out = {}
    for p, v in by_provider.items():
        out[p] = {
            "ok": v["ok"],
            "total": v["total"],
            "rate": v["ok"] / v["total"] if v["total"] else 0.0,
        }
    return {
        "metric": "embedding_provider_uptime",
        "window_hours": hours,
        "by_provider": out,
    }


def auth_failure_rate(store: "XingkongzuoStore", minutes: int = 5) -> dict:
    """M-1.7: Auth 失败率 (401+403 / 总)."""
    since = _now() - timedelta(minutes=minutes)
    events = _events_since(store, "auth.attempt", since)

    total = 0
    fails = 0
    for e in events:
        meta = _parse_meta(e)
        status = meta.get("status")
        total += 1
        if status in (401, 403):
            fails += 1
    return {
        "metric": "auth_failure_rate",
        "window_minutes": minutes,
        "total": total,
        "failures": fails,
        "rate": fails / total if total else 0.0,
    }


def active_clients_30d(store: "XingkongzuoStore") -> dict:
    """M-1.8: 30d 内成功认证的 distinct area_key_prefix 数."""
    since = _now() - timedelta(days=30)
    events = _events_since(store, "auth.attempt", since, limit=200_000)

    prefixes: set[str] = set()
    for e in events:
        meta = _parse_meta(e)
        if meta.get("status") != 200:
            continue
        p = meta.get("area_key_prefix")
        if p and not str(p).startswith("system:"):
            prefixes.add(p)
    return {
        "metric": "active_clients_30d",
        "count": len(prefixes),
        "prefixes": sorted(prefixes),
    }


# ============================================================
# 汇总
# ============================================================


def all_metrics(store: "XingkongzuoStore") -> dict:
    """汇总 17 项指标当前值. 给 W4 上 /api/v1/observability/metrics 端点用."""
    return {
        "L3_value": {
            "w12_completion_rate": w12_completion_rate(store),
            "w4_retention_rate": w4_retention_rate(store),
            "resolution_adoption_rate": resolution_adoption_rate(store),
            "paid_conversion_rate": paid_conversion_rate(store),
        },
        "L2_experience": {
            "session_quality_rate": session_quality_rate(store),
            "session_success_rate": session_success_rate(store),
            "report_generation_p95": report_generation_p95(store),
            "api_error_rate": api_error_rate(store),
            "search_hit_rate": search_hit_rate(store),
        },
        "L1_capacity": {
            "api_read_p95": api_read_p95(store),
            "api_write_p95": api_write_p95(store),
            "embedding_p95": embedding_p95(store),
            "lancedb_query_p95": lancedb_query_p95(store),
            "disk_usage": disk_usage(store),
            "embedding_provider_uptime": embedding_provider_uptime(store),
            "auth_failure_rate": auth_failure_rate(store),
            "active_clients_30d": active_clients_30d(store),
        },
    }
