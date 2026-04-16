"""
Astrolabe MCP HTTP Server - Streamable HTTP transport

与 stdio server (`xingtu_mcp.server`) 共享同一套 tools —— 本模块只改变传输层，
供 Matrix Area 等远程场景直接挂载 MCP URL 使用。

环境变量：
  XINGTU_MCP_HTTP_PORT   监听端口（默认 8100）
  XINGTU_MCP_HTTP_HOST   监听地址（默认 0.0.0.0）
  XINGTU_TENANT_ID       租户 ID（默认 default）
  其他 XINGTU_*           与 stdio 模式共用
"""

from __future__ import annotations

import logging
import os


def main() -> None:
    """启动 MCP HTTP (streamable) 服务器"""
    logging.basicConfig(
        level=os.environ.get("XINGTU_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    logger = logging.getLogger("xingtu.mcp.http")

    port = int(os.environ.get("XINGTU_MCP_HTTP_PORT", "8100"))
    host = os.environ.get("XINGTU_MCP_HTTP_HOST", "0.0.0.0")

    # Override FastMCP settings BEFORE importing server module —
    # FastMCP reads host/port from env at import time via Settings.
    os.environ["FASTMCP_HOST"] = host
    os.environ["FASTMCP_PORT"] = str(port)

    # Import triggers tool registration on the shared `mcp` instance.
    from .server import mcp

    # Ensure host/port are set on the Settings object (redundant but safe).
    mcp.settings.host = host
    mcp.settings.port = port

    tenant = os.environ.get("XINGTU_TENANT_ID", "default")
    logger.info(
        "Starting Astrolabe MCP HTTP on %s:%d (tenant=%s)", host, port, tenant
    )

    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
