"""Observability dashboard 路由测试."""
from __future__ import annotations

import json
import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def setup_env(tmp_path):
    os.environ["XINGTU_DB_PATH"] = str(tmp_path / "obs_api_db")
    os.environ["XINGTU_EMBEDDING_PROVIDER"] = "none"
    os.environ["XINGTU_AUTH_MODE"] = "none"
    yield
    for key in [
        "XINGTU_DB_PATH", "XINGTU_EMBEDDING_PROVIDER", "XINGTU_AUTH_MODE",
        "XINGTU_AREA_KEYS", "XINGTU_TENANT_ID", "XINGTU_CALLER_ID",
    ]:
        os.environ.pop(key, None)


@pytest.fixture(autouse=True)
def reset(setup_env):
    from xingtu_api.deps import reset_service
    reset_service()
    yield
    reset_service()


@pytest.fixture
def client():
    from xingtu_api.main import app
    return TestClient(app)


# ===== Auth =====


class TestAuth:
    def test_metrics_401_when_area_key_required(self, tmp_path):
        os.environ["XINGTU_AUTH_MODE"] = "area_key"
        os.environ["XINGTU_AREA_KEYS"] = "testkey:default"

        from xingtu_api.deps import reset_service
        reset_service()
        from xingtu_api.main import app
        client = TestClient(app)

        resp = client.get("/api/v1/observability/metrics")
        assert resp.status_code == 401

    def test_metrics_200_with_area_key(self, tmp_path):
        os.environ["XINGTU_AUTH_MODE"] = "area_key"
        os.environ["XINGTU_AREA_KEYS"] = "testkey:default"

        from xingtu_api.deps import reset_service
        reset_service()
        from xingtu_api.main import app
        client = TestClient(app)

        resp = client.get(
            "/api/v1/observability/metrics",
            headers={"Authorization": "Bearer testkey"},
        )
        assert resp.status_code == 200


# ===== Metrics endpoint =====


class TestMetricsEndpoint:
    def test_returns_three_sections(self, client):
        resp = client.get("/api/v1/observability/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert set(data.keys()) == {"L3_value", "L2_experience", "L1_capacity"}

    def test_returns_17_metrics(self, client):
        resp = client.get("/api/v1/observability/metrics")
        data = resp.json()
        assert len(data["L3_value"]) == 4
        assert len(data["L2_experience"]) == 5
        assert len(data["L1_capacity"]) == 8

    def test_known_metric_keys_present(self, client):
        resp = client.get("/api/v1/observability/metrics")
        data = resp.json()
        assert "w12_completion_rate" in data["L3_value"]
        assert "session_quality_rate" in data["L2_experience"]
        assert "auth_failure_rate" in data["L1_capacity"]


# ===== Dashboard endpoint =====


class TestDashboard:
    """Dashboard 只展示 9 项基建 (8 L1 + api_error_rate). FYD 8 项业务指标
    不在此 dashboard, 但仍出现在 /metrics JSON (lib all_metrics 不变)."""

    def test_html_response(self, client):
        resp = client.get("/api/v1/observability/dashboard")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")
        body = resp.text
        assert "Astrolabe Observability" in body
        assert "API 健康" in body
        assert "L1 基建容量" in body

    def test_fyd_metrics_excluded_from_dashboard(self, client):
        """FYD 业务指标不在 dashboard 渲染."""
        resp = client.get("/api/v1/observability/dashboard")
        body = resp.text
        assert "L3 价值层" not in body
        assert "W12 完成率" not in body
        assert "议会发言质量" not in body
        assert "付费转化率" not in body

    def test_infra_metrics_in_dashboard(self, client):
        """9 项基建指标都在 dashboard."""
        resp = client.get("/api/v1/observability/dashboard")
        body = resp.text
        for name in [
            "api_error_rate",
            "api_read_p95", "api_write_p95",
            "embedding_p95", "lancedb_query_p95",
            "disk_usage", "embedding_provider_uptime",
            "auth_failure_rate", "active_clients_30d",
        ]:
            assert name in body, f"missing {name} in dashboard"

    def test_no_data_renders_na(self, client):
        """空数据库下大部分指标显示 N/A. active_clients_30d=0 例外: 直接 FAIL."""
        resp = client.get("/api/v1/observability/dashboard")
        body = resp.text
        assert "N/A" in body
        assert "FAIL" in body  # active_clients_30d=0 → FAIL

    def test_metric_label_rendered(self, client):
        """中文 label 渲染."""
        resp = client.get("/api/v1/observability/dashboard")
        body = resp.text
        assert "API 错误率" in body
        assert "Auth 失败率" in body
        assert "30 日活跃客户数" in body

    def test_auto_refresh_meta(self, client):
        resp = client.get("/api/v1/observability/dashboard")
        assert 'http-equiv="refresh"' in resp.text
        assert 'content="60"' in resp.text


# ===== Health endpoint =====


class TestObsHealth:
    def test_health_structure(self, client):
        resp = client.get("/api/v1/observability/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "ok" in data
        assert "failing" in data
        assert isinstance(data["failing"], list)

    def test_health_reports_active_clients_failing(self, client):
        """空 DB: active_clients=0 应进 failing 列表."""
        resp = client.get("/api/v1/observability/health")
        data = resp.json()
        names = [f["name"] for f in data["failing"]]
        assert "active_clients_30d" in names
        assert data["ok"] is False


# ===== Threshold logic with seeded data =====


class TestThresholdRendering:
    def test_auth_failure_renders_fail(self, client):
        """插桩: 10 次 auth.attempt 全 401 → auth_failure_rate=100% > 2% → FAIL."""
        from xingtu_api.deps import get_service
        service = get_service()
        for i in range(10):
            service.events.emit(
                event_type="auth.attempt",
                target_type="metric_event",
                target_id=f"req_{i}",
                after_snapshot=json.dumps({
                    "status": 401,
                    "area_key_prefix": "bad_key",
                    "route": "/api/v1/x",
                }),
            )

        resp = client.get("/api/v1/observability/dashboard")
        body = resp.text
        assert "100.00%" in body
        assert "FAIL" in body
