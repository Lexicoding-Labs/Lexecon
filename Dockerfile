# Multi-stage Dockerfile for Lexecon
# Builds React frontend + Python backend into a single image

# ── Stage 1: Frontend build ──
FROM node:20-slim AS frontend-builder

WORKDIR /frontend

COPY frontend/package.json ./
RUN npm install --no-audit --no-fund

COPY frontend/ .
RUN npm run build

# ── Stage 2: Python build ──
FROM python:3.11-slim AS python-builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install from pyproject.toml only (system-wide so runtime copies cleanly)
COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip install --no-cache-dir .

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

# Copy Python packages from builder (system-wide install)
# Only copy site-packages — do NOT copy /usr/local/bin to avoid overwriting
# the runtime image's own Python binary with the builder's version.
# python -m uvicorn works without uvicorn on PATH.
COPY --from=python-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# Copy application source
COPY --from=python-builder /build/src ./src
COPY --from=python-builder /build/pyproject.toml .

# Copy React build output
COPY --from=frontend-builder /frontend/build ./static

# Copy migrations and startup script
COPY migrations/ ./migrations/
COPY start.sh ./start.sh

# Create data directory
RUN mkdir -p /data/.lexecon && chown -R lexecon:lexecon /data /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    LEXECON_DATA_DIR=/data/.lexecon \
    LEXECON_LOG_LEVEL=INFO \
    LEXECON_LOG_FORMAT=json

# Switch to non-root user
USER lexecon

# Expose port
EXPOSE 8000

# Health check using curl instead of python+requests
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -sf http://localhost:8000/health || exit 1

# Use tini as init system
ENTRYPOINT ["/usr/bin/tini", "--"]

# Run migrations then start server
CMD ["/bin/sh", "/app/start.sh"]
