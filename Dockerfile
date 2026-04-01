# Astrolabe - Docker Image
# Multi-stage build for minimal image size

# ===== Stage 1: Build =====
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --target=/install ".[mcp,cli]"

# ===== Stage 2: Runtime =====
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src:/usr/local/lib/python3.11/site-packages \
    XINGTU_DB_PATH=/data \
    XINGTU_LOG_LEVEL=INFO \
    XINGTU_EMBEDDING_PROVIDER=none

RUN useradd -m -u 1000 xingtu && \
    mkdir -p /data /app && \
    chown -R xingtu:xingtu /data /app

RUN apt-get update && apt-get install -y \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local/lib/python3.11/site-packages

WORKDIR /app

COPY --chown=xingtu:xingtu src ./src
COPY --chown=xingtu:xingtu pyproject.toml README.md entrypoint.py ./

USER xingtu

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD ["python", "/app/entrypoint.py", "--check"]

CMD ["python", "/app/entrypoint.py"]
