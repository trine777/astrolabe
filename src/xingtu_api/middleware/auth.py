"""
Authentication middleware — 多场景验证，自动路由到租户分区。

模式（XINGTU_AUTH_MODE，可逗号组合）：

  none         开发/MCP stdio，env 锁定分区
  area_key     简单 Key→Tenant 映射（轻量部署）
  jwt          JWT Token，从 claims 提取 tenant_id（Web/移动端）
  matrix_hmac  Matrix HMAC 签名验证（Area MCP HTTP 模式）

组合示例：
  XINGTU_AUTH_MODE=area_key,jwt   → 先尝试 area_key，再尝试 jwt
  XINGTU_AUTH_MODE=matrix_hmac    → 仅接受 Matrix 签名请求

环境变量：
  XINGTU_AREA_KEYS    key:tenant 映射（area_key 模式）
  XINGTU_JWT_SECRET   JWT 签名密钥（jwt 模式）
  XINGTU_HMAC_SECRET  HMAC 签名密钥（matrix_hmac 模式）
  XINGTU_TENANT_ID    固定租户（none 模式 / MCP stdio）
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from typing import Dict, List, Optional, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

_PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


# ===== Verifier functions: each returns (tenant_id, caller_id) or None =====


def _verify_area_key(request) -> Optional[Tuple[str, str]]:
    """area_key: Bearer <key> → 查表得 tenant_id。"""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    key = auth[len("Bearer "):]
    raw = os.environ.get("XINGTU_AREA_KEYS", "")
    if not raw:
        return None
    for pair in raw.split(","):
        pair = pair.strip()
        if ":" in pair:
            k, tenant = pair.split(":", 1)
            if k.strip() == key:
                return tenant.strip(), f"key:{key}"
    return None


def _verify_jwt(request) -> Optional[Tuple[str, str]]:
    """jwt: Bearer <token> → 解码 payload，提取 tenant_id + sub。

    使用简易 JWT 解码（HS256），不引入 PyJWT 依赖。
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[len("Bearer "):]
    secret = os.environ.get("XINGTU_JWT_SECRET", "")
    if not secret:
        return None

    parts = token.split(".")
    if len(parts) != 3:
        return None

    try:
        import base64

        # Decode header + payload
        def _b64decode(s: str) -> bytes:
            padding = 4 - len(s) % 4
            return base64.urlsafe_b64decode(s + "=" * padding)

        header = json.loads(_b64decode(parts[0]))
        payload = json.loads(_b64decode(parts[1]))

        # Verify signature (HS256)
        if header.get("alg") != "HS256":
            return None
        signing_input = f"{parts[0]}.{parts[1]}".encode()
        expected_sig = hmac.new(
            secret.encode(), signing_input, hashlib.sha256
        ).digest()
        actual_sig = _b64decode(parts[2])
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None

        # Check expiry
        if "exp" in payload and payload["exp"] < time.time():
            return None

        tenant_id = payload.get("tenant_id") or payload.get("area_id")
        caller_id = payload.get("sub") or payload.get("agent_id", "jwt-user")
        if not tenant_id:
            return None
        return tenant_id, caller_id

    except Exception:
        return None


def _verify_matrix_hmac(request) -> Optional[Tuple[str, str]]:
    """matrix_hmac: X-Matrix-Signature + X-Matrix-Tenant 验证。

    Matrix 在转发请求时签名：
      signature = HMAC-SHA256(secret, tenant_id + ":" + timestamp)
      Headers:
        X-Matrix-Tenant: area-smart-data
        X-Matrix-Timestamp: 1714000000
        X-Matrix-Signature: <hex digest>
    """
    tenant_id = request.headers.get("X-Matrix-Tenant")
    timestamp = request.headers.get("X-Matrix-Timestamp")
    signature = request.headers.get("X-Matrix-Signature")

    if not all([tenant_id, timestamp, signature]):
        return None

    secret = os.environ.get("XINGTU_HMAC_SECRET", "")
    if not secret:
        return None

    # Verify timestamp freshness (5 min window)
    try:
        ts = int(timestamp)
        if abs(time.time() - ts) > 300:
            return None
    except (ValueError, TypeError):
        return None

    # Verify HMAC
    message = f"{tenant_id}:{timestamp}".encode()
    expected = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return None

    caller_id = request.headers.get("X-Caller-ID", f"matrix:{tenant_id}")
    return tenant_id, caller_id


# ===== Verifier registry =====

_VERIFIERS = {
    "area_key": _verify_area_key,
    "jwt": _verify_jwt,
    "matrix_hmac": _verify_matrix_hmac,
}


class AuthMiddleware(BaseHTTPMiddleware):
    """
    多场景认证中间件。

    XINGTU_AUTH_MODE 支持单个或逗号组合：
      none          → env 绑定，直接放行
      area_key      → Bearer key 查表
      jwt           → Bearer JWT 解码
      matrix_hmac   → HMAC 签名验证
      area_key,jwt  → 依次尝试，任一通过即可
    """

    async def dispatch(self, request, call_next):
        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)

        raw_mode = os.environ.get("XINGTU_AUTH_MODE", "none")
        modes = [m.strip() for m in raw_mode.split(",")]

        # none 模式：env 绑定，不验证
        if "none" in modes:
            request.state.tenant_id = os.environ.get("XINGTU_TENANT_ID", "default")
            request.state.caller_id = os.environ.get("XINGTU_CALLER_ID", "anonymous")
            return await call_next(request)

        # 依次尝试每种验证方式
        for mode in modes:
            verifier = _VERIFIERS.get(mode)
            if verifier is None:
                continue
            result = verifier(request)
            if result is not None:
                request.state.tenant_id, request.state.caller_id = result
                return await call_next(request)

        return JSONResponse(
            status_code=401,
            content={
                "detail": "Authentication required",
                "supported_modes": modes,
            },
        )
