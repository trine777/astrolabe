"""星图 XingTu - FastAPI HTTP Server

与 MCP Server 1:1 映射，为非 MCP 客户端（Matrix HTTP MCP、浏览器等）提供 REST 接口。
"""

from __future__ import annotations

import logging

from fastapi import FastAPI

from .middleware.auth import AuthMiddleware
from .routes import collections, documents, search, ingest, metrics, trust, system, matrix_map, observability

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Astrolabe API",
    description="元数据可靠层 HTTP 接口",
    version="2.0.0",
)

# Middleware
app.add_middleware(AuthMiddleware)

# Routes
app.include_router(collections.router, prefix="/api/v1", tags=["collections"])
app.include_router(documents.router, prefix="/api/v1", tags=["documents"])
app.include_router(search.router, prefix="/api/v1", tags=["search"])
app.include_router(ingest.router, prefix="/api/v1", tags=["ingest"])
app.include_router(metrics.router, prefix="/api/v1", tags=["metrics"])
app.include_router(trust.router, prefix="/api/v1", tags=["trust"])
app.include_router(system.router, prefix="/api/v1", tags=["system"])
app.include_router(matrix_map.router, prefix="/api/v1")
app.include_router(observability.router, prefix="/api/v1", tags=["observability"])


@app.get("/health")
def health():
    """Health check endpoint."""
    from .deps import get_service
    service = get_service()
    stats = service.get_stats()
    return {"status": "ok", "stats": stats}


def main():
    """CLI entry point."""
    import uvicorn
    logging.basicConfig(level=logging.INFO)
    logger.info("Astrolabe HTTP Server starting...")
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
