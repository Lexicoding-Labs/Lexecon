# Multi-stage Dockerfile for Lexecon
# Builds React frontend + Python backend into a single image

# ── Stage 1: Frontend build ──
FROM node:20-slim AS frontend-builder

WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --no-audit --no-fund

COPY frontend/ .
RUN npm run build

# ── Stage 2: Python build ──
FROM python:3.11-slim AS python-builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install from pyproject.toml only
COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip install --no-cache-dir --user .

# ── Stage 3: Runtime ──
FROM python:3.11-slim

# Security: Create non-root user
RUN groupadd -r lexecon && useradd -r -g lexecon lexecon

# Install runtime dependencies (tini for init, curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tini \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy Python packages from builder
COPY --from=python-builder /root/.local /home/lexecon/.local

# Copy application source
COPY --from=python-builder /build/src ./src
COPY --from=python-builder /build/pyproject.toml .

# Copy React build output
COPY --from=frontend-builder /frontend/build ./static

# Copy migrations
COPY migrations/ ./migrations/

# Create data directory
RUN mkdir -p /data/.lexecon && chown -R lexecon:lexecon /data

# Set environment variables
ENV PATH=/home/lexecon/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    LEXECON_DATA_DIR=/data/.lexecon \
    LEXECON_LOG_LEVEL=INFO \
    LEXECON_LOG_FORMAT=json

# Switch to non-root user
USER lexecon

# Expose port
EXPOSE 8000

# Health check using curl instead of python+requests
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -sf http://localhost:8000/health || exit 1

# Use tini as init system
ENTRYPOINT ["/usr/bin/tini", "--"]

# Run server
CMD sh -c "python -m uvicorn lexecon.api.server:app --host 0.0.0.0 --port ${PORT:-8000}"
