"""FastAPI dependencies — service instance + tenant context."""

from __future__ import annotations

from typing import Optional

from fastapi import Request

from xingtu import XingTuService
from xingtu.config import XingTuConfig

_service: Optional[XingTuService] = None


def get_service() -> XingTuService:
    global _service
    if _service is None:
        config = XingTuConfig.from_env()
        _service = XingTuService(config)
        _service.initialize()
    return _service


def reset_service() -> None:
    """Reset for testing."""
    global _service
    _service = None


def get_tenant(request: Request) -> str:
    """从 request.state 获取 tenant_id（由 AuthMiddleware 注入）。"""
    return getattr(request.state, "tenant_id", "default")
