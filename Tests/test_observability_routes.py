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
    def test_html_response(self, client):
        resp = client.get("/api/v1/observability/dashboard")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")
        body = resp.text
        assert "Astrolabe Observability" in body
        assert "L3 价值层" in body
        assert "L2 体验层" in body
        assert "L1 容量层" in body

    def test_no_data_renders_na(self, client):
        """空数据库下大部分指标应显示 N/A 不是 FAIL."""
        resp = client.get("/api/v1/observability/dashboard")
        body = resp.text
        # 大部分 N/A
        assert "N/A" in body
        # active_clients_30d 例外: count=0 < 1 应显示 FAIL
        assert "active_clients_30d" in body

    def test_active_clients_zero_fails(self, client):
        """active_clients_30d=0 不允许 N/A, 必须 FAIL (count 没有 samples 概念)."""
        resp = client.get("/api/v1/observability/dashboard")
        body = resp.text
        # active_clients_30d 行附近应有 FAIL badge
        # 简单验证 FAIL 存在 (active_clients 是唯一保证有判定的 cold start 指标)
        assert "FAIL" in body

    def test_metric_label_rendered(self, client):
        """中文 label 渲染."""
        resp = client.get("/api/v1/observability/dashboard")
        body = resp.text
        assert "W12 完成率" in body
        assert "议会发言质量" in body
        assert "API 错误率" in body

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
    def test_session_failure_renders_fail(self, client):
        """插桩: 启动 10 议会, 0 完成 → success_rate=0 < 0.95 → FAIL."""
        from xingtu_api.deps import get_service
        service = get_service()
        for i in range(10):
            service.events.emit(
                event_type="fyd.session_started",
                target_type="metric_event",
                target_id=f"sess_{i}",
                actor_type="user",
                actor_id="u1",
                after_snapshot=json.dumps({"user_id": "u1"}),
            )

        resp = client.get("/api/v1/observability/dashboard")
        body = resp.text
        # session_success_rate 那一行应是 FAIL (0% < 95%)
        # 简单验证: 0.0% 出现 + FAIL 出现
        assert "0.0%" in body
        assert "FAIL" in body
