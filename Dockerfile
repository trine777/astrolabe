# 星图 XingTu - Docker 镜像
# 多阶段构建，优化镜像大小

# ===== 阶段 1: 构建阶段 =====
FROM python:3.11-slim as builder

# 设置工作目录
WORKDIR /build

# 安装构建依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY pyproject.toml README.md ./
COPY src ./src

# 安装 Python 依赖到独立目录
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --target=/install \
    ".[mcp,embeddings-local]"

# ===== 阶段 2: 运行阶段 =====
FROM python:3.11-slim

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    XINGTU_DATA_DIR=/data \
    XINGTU_LOG_LEVEL=INFO

# 创建非 root 用户
RUN useradd -m -u 1000 xingtu && \
    mkdir -p /data /app && \
    chown -R xingtu:xingtu /data /app

# 安装运行时依赖
RUN apt-get update && apt-get install -y \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 复制 Python 依赖
COPY --from=builder /install /usr/local/lib/python3.11/site-packages

# 设置工作目录
WORKDIR /app

# 复制应用代码
COPY --chown=xingtu:xingtu src ./src
COPY --chown=xingtu:xingtu pyproject.toml README.md ./

# 切换到非 root 用户
USER xingtu

# 暴露 MCP 服务端口（stdio 模式不需要端口，但保留以备将来使用）
# EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from xingtu import XingTuService; s = XingTuService(); s.initialize(); print('OK')" || exit 1

# 默认命令：保持容器运行，等待 MCP 连接
CMD ["tail", "-f", "/dev/null"]
