"""Observability routes — 17 项指标 JSON + HTML dashboard.

Single source of truth for thresholds: `_SPECS` below.
spec: docs/metrics/EVENT_SCHEMA.md
"""
from __future__ import annotations

import html
from typing import Any, Callable, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from xingtu import observability as obs

from ..deps import get_service, get_tenant

router = APIRouter()


# ============================================================
# 指标 spec — 阈值 single source of truth
# ============================================================
#
# 每条:
#   name          all_metrics() 输出里的 key
#   section       L3_value / L2_experience / L1_capacity
#   label         dashboard 显示中文名
#   extract       从 metric dict 取要被阈值判定的标量
#   op            ">=" | "<=" | "<" | ">"
#   threshold     阈值
#   format        值的可读字符串
#   threshold_str 阈值的可读字符串


def _min_provider_rate(m: dict) -> float:
    bp = m.get("by_provider") or {}
    rates = [p.get("rate", 0.0) for p in bp.values()]
    return min(rates) if rates else 1.0


_SPECS: list[dict] = [
    # L3 价值
    {
        "name": "w12_completion_rate", "section": "L3_value", "label": "W12 完成率",
        "extract": lambda m: m.get("rate", 0.0),
        "op": ">=", "threshold": 0.30,
        "format": lambda v: f"{v * 100:.1f}%", "threshold_str": "≥30%",
    },
    {
        "name": "w4_retention_rate", "section": "L3_value", "label": "W4 留存率",
        "extract": lambda m: m.get("rate", 0.0),
        "op": ">=", "threshold": 0.50,
        "format": lambda v: f"{v * 100:.1f}%", "threshold_str": "≥50%",
    },
    {
        "name": "resolution_adoption_rate", "section": "L3_value", "label": "决议采纳率",
        "extract": lambda m: m.get("rate", 0.0),
        "op": ">=", "threshold": 0.40,
        "format": lambda v: f"{v * 100:.1f}%", "threshold_str": "≥40%",
    },
    {
        "name": "paid_conversion_rate", "section": "L3_value", "label": "付费转化率",
        "extract": lambda m: m.get("rate", 0.0),
        "op": ">=", "threshold": 0.15,
        "format": lambda v: f"{v * 100:.1f}%", "threshold_str": "≥15%",
    },
    # L2 体验
    {
        "name": "session_quality_rate", "section": "L2_experience", "label": "议会发言质量",
        "extract": lambda m: m.get("rate", 0.0),
        "op": ">=", "threshold": 0.80,
        "format": lambda v: f"{v * 100:.1f}%", "threshold_str": "≥80%",
    },
    {
        "name": "session_success_rate", "section": "L2_experience", "label": "议会成功率",
        "extract": lambda m: m.get("rate", 0.0),
        "op": ">=", "threshold": 0.95,
        "format": lambda v: f"{v * 100:.1f}%", "threshold_str": "≥95%",
    },
    {
        "name": "report_generation_p95", "section": "L2_experience", "label": "报告生成 p95",
        "extract": lambda m: m.get("p95_seconds", 0.0),
        "op": "<=", "threshold": 90.0,
        "format": lambda v: f"{v:.1f}s", "threshold_str": "≤90s",
    },
    {
        "name": "api_error_rate", "section": "L2_experience", "label": "API 错误率",
        "extract": lambda m: m.get("rate", 0.0),
        "op": "<", "threshold": 0.01,
        "format": lambda v: f"{v * 100:.2f}%", "threshold_str": "<1%",
    },
    {
        "name": "search_hit_rate", "section": "L2_experience", "label": "搜索命中率",
        "extract": lambda m: m.get("rate", 0.0),
        "op": ">=", "threshold": 0.70,
        "format": lambda v: f"{v * 100:.1f}%", "threshold_str": "≥70%",
    },
    # L1 容量
    {
        "name": "api_read_p95", "section": "L1_capacity", "label": "API read p95",
        "extract": lambda m: m.get("p95_ms", 0.0),
        "op": "<=", "threshold": 300.0,
        "format": lambda v: f"{v:.0f}ms", "threshold_str": "≤300ms",
    },
    {
        "name": "api_write_p95", "section": "L1_capacity", "label": "API write p95",
        "extract": lambda m: m.get("p95_ms", 0.0),
        "op": "<=", "threshold": 500.0,
        "format": lambda v: f"{v:.0f}ms", "threshold_str": "≤500ms",
    },
    {
        "name": "embedding_p95", "section": "L1_capacity", "label": "Embedding p95",
        "extract": lambda m: m.get("p95_ms", 0.0),
        "op": "<=", "threshold": 1000.0,
        "format": lambda v: f"{v:.0f}ms", "threshold_str": "≤1000ms",
    },
    {
        "name": "lancedb_query_p95", "section": "L1_capacity", "label": "LanceDB 查询 p95",
        "extract": lambda m: m.get("p95_ms", 0.0),
        "op": "<=", "threshold": 100.0,
        "format": lambda v: f"{v:.0f}ms", "threshold_str": "≤100ms",
    },
    {
        "name": "disk_usage", "section": "L1_capacity", "label": "磁盘占用",
        "extract": lambda m: m.get("ratio", 0.0),
        "op": "<", "threshold": 0.70,
        "format": lambda v: f"{v * 100:.1f}%", "threshold_str": "<70%",
    },
    {
        "name": "embedding_provider_uptime", "section": "L1_capacity", "label": "Embedding provider 可用率",
        "extract": _min_provider_rate,
        "op": ">=", "threshold": 0.99,
        "format": lambda v: f"{v * 100:.2f}%", "threshold_str": "≥99%",
    },
    {
        "name": "auth_failure_rate", "section": "L1_capacity", "label": "Auth 失败率",
        "extract": lambda m: m.get("rate", 0.0),
        "op": "<", "threshold": 0.02,
        "format": lambda v: f"{v * 100:.2f}%", "threshold_str": "<2%",
    },
    {
        "name": "active_clients_30d", "section": "L1_capacity", "label": "30 日活跃客户数",
        "extract": lambda m: m.get("count", 0),
        "op": ">=", "threshold": 1,
        "format": lambda v: f"{int(v)}", "threshold_str": "≥1",
    },
]


_SECTION_LABELS = {
    "L3_value": "L3 价值层",
    "L2_experience": "L2 体验层",
    "L1_capacity": "L1 容量层",
}


def _passes(value: float, op: str, threshold: float) -> bool:
    if op == ">=":
        return value >= threshold
    if op == ">":
        return value > threshold
    if op == "<=":
        return value <= threshold
    if op == "<":
        return value < threshold
    return False


def _evaluate(spec: dict, raw: dict) -> dict:
    """单条 spec 评估 — 返回 dashboard 渲染需要的字段."""
    metric = raw.get(spec["section"], {}).get(spec["name"], {})
    samples_n = (
        metric.get("samples")
        or metric.get("scored")
        or metric.get("started")
        or metric.get("total")
        or metric.get("count")
        or 0
    )
    if samples_n == 0 and spec["name"] != "active_clients_30d":
        # 冷启动: 没数据视为 N/A, 不染红
        return {
            **spec, "raw": metric,
            "value": None, "value_str": "—",
            "passing": True, "no_data": True,
        }

    value = spec["extract"](metric)
    return {
        **spec, "raw": metric,
        "value": value,
        "value_str": spec["format"](value),
        "passing": _passes(value, spec["op"], spec["threshold"]),
        "no_data": False,
    }


# ============================================================
# Endpoints
# ============================================================


@router.get("/observability/metrics")
def get_metrics(tenant_id: str = Depends(get_tenant)) -> dict:
    """Raw 17 项指标 JSON. 返回 obs.all_metrics() 原始结构."""
    service = get_service()
    return obs.all_metrics(service.store)


@router.get("/observability/health")
def get_observability_health(tenant_id: str = Depends(get_tenant)) -> dict:
    """阈值汇总: ok=true 表示无红灯, failing=红灯指标列表."""
    service = get_service()
    raw = obs.all_metrics(service.store)
    failing = []
    for spec in _SPECS:
        evaluated = _evaluate(spec, raw)
        if not evaluated["passing"] and not evaluated["no_data"]:
            failing.append({
                "name": spec["name"],
                "section": spec["section"],
                "label": spec["label"],
                "value": evaluated["value_str"],
                "threshold": spec["threshold_str"],
            })
    return {"ok": len(failing) == 0, "failing": failing}


@router.get("/observability/dashboard", response_class=HTMLResponse)
def get_dashboard(tenant_id: str = Depends(get_tenant)) -> HTMLResponse:
    """HTML 表格 dashboard. 60s 自动刷新."""
    service = get_service()
    raw = obs.all_metrics(service.store)
    return HTMLResponse(_render_dashboard(raw))


# ============================================================
# HTML 渲染
# ============================================================


_HTML_BASE = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="60">
<title>Astrolabe Observability</title>
<style>
  body {{ font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
         max-width: 960px; margin: 2em auto; padding: 0 1em; color: #222; }}
  h1 {{ font-size: 1.4em; margin-bottom: 0.2em; }}
  .meta {{ color: #888; font-size: 0.85em; margin-bottom: 2em; }}
  h2 {{ font-size: 1.1em; margin-top: 2em; border-bottom: 1px solid #ddd; padding-bottom: 0.3em; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 0.92em; }}
  th, td {{ text-align: left; padding: 0.5em 0.7em; border-bottom: 1px solid #eee; }}
  th {{ background: #fafafa; font-weight: 600; }}
  td.value {{ font-family: ui-monospace, "SF Mono", monospace; font-variant-numeric: tabular-nums; }}
  .pass {{ color: #1a7f37; font-weight: 600; }}
  .fail {{ color: #cf222e; font-weight: 600; }}
  .nodata {{ color: #888; }}
  .badge {{ display: inline-block; padding: 0.1em 0.5em; border-radius: 0.3em;
            font-size: 0.78em; font-weight: 600; }}
  .badge.pass {{ background: #dafbe1; color: #1a7f37; }}
  .badge.fail {{ background: #ffebe9; color: #cf222e; }}
  .badge.nodata {{ background: #eee; color: #888; }}
</style>
</head>
<body>
<h1>Astrolabe Observability</h1>
<div class="meta">17 项指标 · 60 秒自动刷新 · spec: <code>docs/metrics/EVENT_SCHEMA.md</code></div>
{sections}
</body>
</html>
"""


def _render_dashboard(raw: dict) -> str:
    sections_html = []
    for section_key, section_label in _SECTION_LABELS.items():
        rows_html = []
        for spec in _SPECS:
            if spec["section"] != section_key:
                continue
            ev = _evaluate(spec, raw)
            label = html.escape(spec["label"])
            name = html.escape(spec["name"])
            threshold = html.escape(spec["threshold_str"])
            value_str = html.escape(ev["value_str"])

            if ev["no_data"]:
                badge = '<span class="badge nodata">N/A</span>'
                value_class = "value nodata"
            elif ev["passing"]:
                badge = '<span class="badge pass">PASS</span>'
                value_class = "value pass"
            else:
                badge = '<span class="badge fail">FAIL</span>'
                value_class = "value fail"

            rows_html.append(
                f"<tr><td>{label}</td>"
                f"<td><code>{name}</code></td>"
                f"<td class=\"{value_class}\">{value_str}</td>"
                f"<td>{threshold}</td>"
                f"<td>{badge}</td></tr>"
            )
        sections_html.append(
            f"<h2>{html.escape(section_label)}</h2>"
            f"<table><thead><tr><th>指标</th><th>name</th>"
            f"<th>当前值</th><th>阈值</th><th>状态</th></tr></thead>"
            f"<tbody>{''.join(rows_html)}</tbody></table>"
        )
    return _HTML_BASE.format(sections="\n".join(sections_html))
