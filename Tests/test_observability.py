"""可观测性指标 — 烟雾测试 (空数据 + 端到端最小路径)."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from xingtu import observability as obs
from xingtu.events import YinglanxuanEvents
from xingtu.store import XingkongzuoStore


@pytest.fixture
def store(tmp_path):
    s = XingkongzuoStore(str(tmp_path / "obs_db"))
    s.initialize()
    return s


@pytest.fixture
def events(store):
    return YinglanxuanEvents(store)


def _emit(events, event_type, target_id, meta, ts=None, actor_id=None):
    """事件 emit 帮手 — 复用约定: target_type=metric_event, after_snapshot=meta JSON."""
    e = events.emit(
        event_type=event_type,
        target_type="metric_event",
        target_id=target_id,
        actor_type="user" if actor_id else "system",
        actor_id=actor_id,
        after_snapshot=json.dumps(meta, ensure_ascii=False),
    )
    if ts:
        # 改写时间戳 (默认是 now), 便于测试历史窗口 — 直接改 store 行不便, 我们只做 now-relative 测试
        pass
    return e


class TestEmptyData:
    """全部 17 个指标在空数据库上不抛错, 返回 rate=0."""

    def test_l3_empty(self, store):
        assert obs.w12_completion_rate(store)["rate"] == 0.0
        assert obs.w4_retention_rate(store)["rate"] == 0.0
        assert obs.resolution_adoption_rate(store)["rate"] == 0.0
        assert obs.paid_conversion_rate(store)["rate"] == 0.0

    def test_l2_empty(self, store):
        assert obs.session_quality_rate(store)["rate"] == 0.0
        assert obs.session_success_rate(store)["rate"] == 0.0
        assert obs.report_generation_p95(store)["samples"] == 0
        assert obs.api_error_rate(store)["rate"] == 0.0
        assert obs.search_hit_rate(store)["rate"] == 0.0

    def test_l1_empty(self, store):
        assert obs.api_read_p95(store)["samples"] == 0
        assert obs.api_write_p95(store)["samples"] == 0
        assert obs.embedding_p95(store)["samples"] == 0
        assert obs.lancedb_query_p95(store)["samples"] == 0
        assert obs.disk_usage(store)["ratio"] == 0.0
        assert obs.embedding_provider_uptime(store)["by_provider"] == {}
        assert obs.auth_failure_rate(store)["rate"] == 0.0
        assert obs.active_clients_30d(store)["count"] == 0

    def test_all_metrics_empty(self, store):
        result = obs.all_metrics(store)
        assert set(result.keys()) == {"L3_value", "L2_experience", "L1_capacity"}
        assert len(result["L3_value"]) == 4
        assert len(result["L2_experience"]) == 5
        assert len(result["L1_capacity"]) == 8


class TestSessionSuccess:
    """M-2.2: 议会成功率 — 启动 3 / 完成 2 / 用户取消 1 → 分母 2 分子 2 = 100%."""

    def test_user_cancel_excluded(self, store, events):
        sids = [f"sess_{i}" for i in range(3)]
        for sid in sids:
            _emit(events, "fyd.session_started", sid, {"user_id": "u1"})
        # 1 完成
        _emit(events, "fyd.session_completed", sids[0], {"user_id": "u1", "week_number": 1})
        # 1 完成
        _emit(events, "fyd.session_completed", sids[1], {"user_id": "u1", "week_number": 2})
        # 1 用户取消
        _emit(events, "fyd.session_failed", sids[2], {"user_id": "u1", "cancel_reason": "user_cancel"})

        result = obs.session_success_rate(store, hours=24)
        assert result["started"] == 2  # 取消的从分母剔除
        assert result["completed"] == 2
        assert result["user_canceled"] == 1
        assert result["rate"] == 1.0


class TestQualityRate:
    """M-2.1: 4 个评分 [3, 4, 5, 5] → 阈值 4 → 75%."""

    def test_threshold_filter(self, store, events):
        for i, score in enumerate([3, 4, 5, 5]):
            _emit(events, "fyd.session_scored", f"sess_{i}", {
                "session_id": f"sess_{i}",
                "score": score,
                "scorer": "trine",
            })
        result = obs.session_quality_rate(store, days=7, threshold=4)
        assert result["scored"] == 4
        assert result["high_quality"] == 3
        assert result["rate"] == 0.75


class TestApiErrorRate:
    """M-2.4: 3xx/4xx/5xx 混合 → 只算 5xx."""

    def test_only_5xx_counted(self, store, events):
        for status in [200, 200, 200, 404, 422, 500, 503]:
            _emit(events, "api.request", str(uuid.uuid4()), {
                "route": "/api/v1/x",
                "method": "GET",
                "status": status,
                "latency_ms": 10,
            })
        result = obs.api_error_rate(store, minutes=5)
        assert result["total"] == 7
        assert result["errors_5xx"] == 2
        assert result["rate"] == pytest.approx(2 / 7)


class TestPercentile:
    """工具函数 _percentile 校验."""

    def test_basic(self):
        # [1..100] 的 p50=50.5, p95=95.05
        values = list(range(1, 101))
        assert obs._percentile(values, 50) == pytest.approx(50.5)
        assert obs._percentile(values, 95) == pytest.approx(95.05)

    def test_empty(self):
        assert obs._percentile([], 95) == 0.0

    def test_single(self):
        assert obs._percentile([42.0], 95) == 42.0
