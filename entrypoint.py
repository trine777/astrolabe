"""Astrolabe Docker entrypoint — 启动 FastAPI HTTP server."""
import os
import sys

sys.path.insert(0, "/app/src")


def healthcheck():
    """Docker HEALTHCHECK: 仅 import 测试, 不调 API."""
    from xingtu.store import XingkongzuoStore  # noqa: F401
    print("OK")


def main():
    """启动 uvicorn 跑 xingtu_api.main:app."""
    import logging
    import uvicorn

    logging.basicConfig(
        level=os.environ.get("XINGTU_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger = logging.getLogger("astrolabe")

    # fly.io 注入 PORT, 默认 8080 (与 fly.toml internal_port 对齐)
    port = int(os.environ.get("PORT", "8080"))
    host = os.environ.get("HOST", "0.0.0.0")

    logger.info(
        f"Astrolabe HTTP server starting on {host}:{port} "
        f"(db={os.environ.get('XINGTU_DB_PATH', '/data')})"
    )
    uvicorn.run(
        "xingtu_api.main:app",
        host=host,
        port=port,
        log_level=os.environ.get("XINGTU_LOG_LEVEL", "info").lower(),
        access_log=True,
    )


if __name__ == "__main__":
    if "--check" in sys.argv:
        healthcheck()
    else:
        main()
