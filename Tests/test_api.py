"""
星图 XingTu - HTTP API 测试

测试 FastAPI 路由 + 多租户隔离 + 认证中间件。
"""

from __future__ import annotations

import json
import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def setup_env(tmp_path):
    os.environ["XINGTU_DB_PATH"] = str(tmp_path / "test_api_db")
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


# ===== Health =====


class TestHealth:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "stats" in data


# ===== Collections =====


class TestCollections:
    def test_create_and_list(self, client):
        resp = client.post("/api/v1/collections", params={"name": "测试集合"})
        assert resp.status_code == 200
        cid = resp.json()["id"]

        resp = client.get("/api/v1/collections")
        assert resp.status_code == 200
        names = [c["name"] for c in resp.json()]
        assert "测试集合" in names

    def test_get_collection(self, client):
        resp = client.post("/api/v1/collections", params={"name": "detail"})
        cid = resp.json()["id"]
        resp = client.get(f"/api/v1/collections/{cid}")
        assert resp.json()["name"] == "detail"

    def test_update_collection(self, client):
        resp = client.post("/api/v1/collections", params={"name": "old"})
        cid = resp.json()["id"]
        resp = client.put(f"/api/v1/collections/{cid}", params={"name": "new"})
        assert resp.json()["name"] == "new"

    def test_delete_collection(self, client):
        resp = client.post("/api/v1/collections", params={"name": "to_delete"})
        cid = resp.json()["id"]
        resp = client.delete(f"/api/v1/collections/{cid}")
        assert resp.json()["status"] == "deleted"


# ===== Documents =====


class TestDocuments:
    def test_add_and_get(self, client):
        resp = client.post("/api/v1/collections", params={"name": "docs"})
        cid = resp.json()["id"]

        resp = client.post("/api/v1/documents", json={
            "collection_id": cid, "texts": ["hello", "world"],
        })
        assert resp.json()["documents_added"] == 2

    def test_batch_get(self, client):
        resp = client.post("/api/v1/collections", params={"name": "batch"})
        cid = resp.json()["id"]
        resp = client.post("/api/v1/documents", json={
            "collection_id": cid, "texts": ["a", "b"],
        })
        ids = resp.json()["document_ids"]

        resp = client.post("/api/v1/documents/batch", json={"document_ids": ids})
        assert len(resp.json()) == 2


# ===== Ingest =====


class TestIngest:
    def test_ingest_file(self, client, tmp_path):
        txt = tmp_path / "test.txt"
        txt.write_text("hello world", encoding="utf-8")
        resp = client.post("/api/v1/ingest/file", params={"file_path": str(txt)})
        assert resp.json()["documents_added"] == 1


# ===== Trust =====


class TestTrust:
    def test_evaluate_trust(self, client):
        resp = client.post("/api/v1/collections", params={"name": "trust_test"})
        cid = resp.json()["id"]
        resp = client.get(f"/api/v1/trust/{cid}")
        assert "trust_score" in resp.json()

    def test_batch_trust(self, client):
        resp = client.post("/api/v1/trust/batch", json={"item_ids": ["nonexist"]})
        assert isinstance(resp.json(), list)


# ===== System =====


class TestSystem:
    def test_stats(self, client):
        resp = client.get("/api/v1/stats")
        assert "collections" in resp.json()

    def test_world_model(self, client):
        resp = client.get("/api/v1/world-model")
        assert "collections" in resp.json()

    def test_projection_l0(self, client):
        resp = client.get("/api/v1/projection/l0")
        assert resp.json()["level"] == "L0"


# ===== Multi-Tenant Isolation =====


def _make_jwt(payload: dict, secret: str) -> str:
    """生成 HS256 JWT token（测试辅助）"""
    import base64
    import hashlib
    import hmac as _hmac

    def _b64encode(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    header = _b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body = _b64encode(json.dumps(payload).encode())
    signing_input = f"{header}.{body}".encode()
    sig = _hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    return f"{header}.{body}.{_b64encode(sig)}"


def _make_hmac_headers(tenant_id: str, secret: str) -> dict:
    """生成 Matrix HMAC 签名 headers（测试辅助）"""
    import hashlib
    import hmac as _hmac
    ts = str(int(__import__("time").time()))
    sig = _hmac.new(
        secret.encode(), f"{tenant_id}:{ts}".encode(), hashlib.sha256
    ).hexdigest()
    return {
        "X-Matrix-Tenant": tenant_id,
        "X-Matrix-Timestamp": ts,
        "X-Matrix-Signature": sig,
    }


class TestMultiTenant:
    def test_area_key_isolation(self, client):
        """不同 Area Key 自动路由到不同分区，数据互不可见"""
        os.environ["XINGTU_AUTH_MODE"] = "area_key"
        os.environ["XINGTU_AREA_KEYS"] = "ak-sd:area-smart-data,ak-defi:area-defi"

        # Tenant A 创建集合
        resp = client.post(
            "/api/v1/collections",
            params={"name": "sales"},
            headers={"Authorization": "Bearer ak-sd"},
        )
        assert resp.status_code == 200
        assert resp.json()["tenant_id"] == "area-smart-data"

        # Tenant B 创建同名集合 — 不同分区，互不冲突
        resp = client.post(
            "/api/v1/collections",
            params={"name": "sales"},
            headers={"Authorization": "Bearer ak-defi"},
        )
        assert resp.status_code == 200
        assert resp.json()["tenant_id"] == "area-defi"

        # Tenant A 只看到自己的
        resp = client.get(
            "/api/v1/collections",
            headers={"Authorization": "Bearer ak-sd"},
        )
        collections = resp.json()
        assert len(collections) == 1
        assert collections[0]["tenant_id"] == "area-smart-data"

        # Tenant B 只看到自己的
        resp = client.get(
            "/api/v1/collections",
            headers={"Authorization": "Bearer ak-defi"},
        )
        collections = resp.json()
        assert len(collections) == 1
        assert collections[0]["tenant_id"] == "area-defi"

    def test_invalid_area_key(self, client):
        """无效 key → 401"""
        os.environ["XINGTU_AUTH_MODE"] = "area_key"
        os.environ["XINGTU_AREA_KEYS"] = "ak-sd:area-smart-data"

        resp = client.get(
            "/api/v1/stats",
            headers={"Authorization": "Bearer wrong-key"},
        )
        assert resp.status_code == 401

    def test_missing_bearer(self, client):
        """不带 Bearer → 401"""
        os.environ["XINGTU_AUTH_MODE"] = "area_key"
        os.environ["XINGTU_AREA_KEYS"] = "ak-sd:area-smart-data"

        resp = client.get("/api/v1/stats")
        assert resp.status_code == 401

    def test_env_tenant_binding(self, client):
        """XINGTU_AUTH_MODE=none 时，用 XINGTU_TENANT_ID 环境变量锁定分区"""
        os.environ["XINGTU_TENANT_ID"] = "area-mcp-bound"

        resp = client.post("/api/v1/collections", params={"name": "mcp_data"})
        assert resp.json()["tenant_id"] == "area-mcp-bound"

        resp = client.get("/api/v1/collections")
        assert len(resp.json()) == 1
        assert resp.json()[0]["tenant_id"] == "area-mcp-bound"


# ===== Authentication =====


class TestAuth:
    def test_no_auth_mode(self, client):
        """XINGTU_AUTH_MODE=none 时所有请求通过"""
        resp = client.get("/api/v1/stats")
        assert resp.status_code == 200

    def test_health_skips_auth(self, client):
        """Health endpoint 跳过认证"""
        os.environ["XINGTU_AUTH_MODE"] = "area_key"
        os.environ["XINGTU_AREA_KEYS"] = "ak:tenant"
        resp = client.get("/health")
        assert resp.status_code == 200


class TestJWTAuth:
    """JWT Token 认证测试"""

    def test_jwt_valid(self, client):
        os.environ["XINGTU_AUTH_MODE"] = "jwt"
        os.environ["XINGTU_JWT_SECRET"] = "test-jwt-secret"

        token = _make_jwt(
            {"tenant_id": "area-jwt", "sub": "user-1"},
            "test-jwt-secret",
        )
        resp = client.post(
            "/api/v1/collections",
            params={"name": "jwt_col"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["tenant_id"] == "area-jwt"

    def test_jwt_wrong_secret(self, client):
        os.environ["XINGTU_AUTH_MODE"] = "jwt"
        os.environ["XINGTU_JWT_SECRET"] = "correct-secret"

        token = _make_jwt(
            {"tenant_id": "area-x", "sub": "user-1"},
            "wrong-secret",
        )
        resp = client.get(
            "/api/v1/stats",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401

    def test_jwt_expired(self, client):
        os.environ["XINGTU_AUTH_MODE"] = "jwt"
        os.environ["XINGTU_JWT_SECRET"] = "secret"

        token = _make_jwt(
            {"tenant_id": "area-x", "sub": "user-1", "exp": 1000000},
            "secret",
        )
        resp = client.get(
            "/api/v1/stats",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401

    def test_jwt_missing_tenant(self, client):
        os.environ["XINGTU_AUTH_MODE"] = "jwt"
        os.environ["XINGTU_JWT_SECRET"] = "secret"

        token = _make_jwt({"sub": "user-1"}, "secret")  # no tenant_id
        resp = client.get(
            "/api/v1/stats",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401

    def test_jwt_with_area_id_claim(self, client):
        """area_id claim 也能用（兼容 Matrix 命名）"""
        os.environ["XINGTU_AUTH_MODE"] = "jwt"
        os.environ["XINGTU_JWT_SECRET"] = "secret"

        token = _make_jwt(
            {"area_id": "area-matrix", "sub": "agent-1"},
            "secret",
        )
        resp = client.post(
            "/api/v1/collections",
            params={"name": "matrix_col"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["tenant_id"] == "area-matrix"


class TestMatrixHMACAuth:
    """Matrix HMAC 签名认证测试"""

    def test_hmac_valid(self, client):
        os.environ["XINGTU_AUTH_MODE"] = "matrix_hmac"
        os.environ["XINGTU_HMAC_SECRET"] = "hmac-secret"

        headers = _make_hmac_headers("area-smart-data", "hmac-secret")
        resp = client.post(
            "/api/v1/collections",
            params={"name": "hmac_col"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["tenant_id"] == "area-smart-data"

    def test_hmac_wrong_secret(self, client):
        os.environ["XINGTU_AUTH_MODE"] = "matrix_hmac"
        os.environ["XINGTU_HMAC_SECRET"] = "correct-secret"

        headers = _make_hmac_headers("area-x", "wrong-secret")
        resp = client.get("/api/v1/stats", headers=headers)
        assert resp.status_code == 401

    def test_hmac_expired_timestamp(self, client):
        """时间戳超过 5 分钟 → 拒绝"""
        import hashlib
        import hmac as _hmac

        os.environ["XINGTU_AUTH_MODE"] = "matrix_hmac"
        os.environ["XINGTU_HMAC_SECRET"] = "secret"

        old_ts = str(int(__import__("time").time()) - 600)
        sig = _hmac.new(
            b"secret", f"area-x:{old_ts}".encode(), hashlib.sha256
        ).hexdigest()
        resp = client.get("/api/v1/stats", headers={
            "X-Matrix-Tenant": "area-x",
            "X-Matrix-Timestamp": old_ts,
            "X-Matrix-Signature": sig,
        })
        assert resp.status_code == 401

    def test_hmac_with_caller_id(self, client):
        """X-Caller-ID 被透传为 caller 标识"""
        os.environ["XINGTU_AUTH_MODE"] = "matrix_hmac"
        os.environ["XINGTU_HMAC_SECRET"] = "secret"

        headers = _make_hmac_headers("area-sd", "secret")
        headers["X-Caller-ID"] = "agent-smart-data"
        resp = client.get("/api/v1/stats", headers=headers)
        assert resp.status_code == 200


class TestComboAuth:
    """组合认证模式测试"""

    def test_area_key_or_jwt(self, client):
        """area_key,jwt — 两种方式都能通过"""
        os.environ["XINGTU_AUTH_MODE"] = "area_key,jwt"
        os.environ["XINGTU_AREA_KEYS"] = "ak-test:area-key-tenant"
        os.environ["XINGTU_JWT_SECRET"] = "jwt-secret"

        # area_key 方式
        resp = client.post(
            "/api/v1/collections",
            params={"name": "by_key"},
            headers={"Authorization": "Bearer ak-test"},
        )
        assert resp.status_code == 200
        assert resp.json()["tenant_id"] == "area-key-tenant"

        # JWT 方式
        token = _make_jwt(
            {"tenant_id": "area-jwt-tenant", "sub": "user-1"},
            "jwt-secret",
        )
        resp = client.post(
            "/api/v1/collections",
            params={"name": "by_jwt"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["tenant_id"] == "area-jwt-tenant"

        # 两者都不匹配 → 401
        resp = client.get(
            "/api/v1/stats",
            headers={"Authorization": "Bearer invalid"},
        )
        assert resp.status_code == 401

    def test_all_three(self, client):
        """area_key,jwt,matrix_hmac — 三种都接受"""
        os.environ["XINGTU_AUTH_MODE"] = "area_key,jwt,matrix_hmac"
        os.environ["XINGTU_AREA_KEYS"] = "ak:t1"
        os.environ["XINGTU_JWT_SECRET"] = "js"
        os.environ["XINGTU_HMAC_SECRET"] = "hs"

        # HMAC
        headers = _make_hmac_headers("t3", "hs")
        resp = client.get("/api/v1/stats", headers=headers)
        assert resp.status_code == 200
