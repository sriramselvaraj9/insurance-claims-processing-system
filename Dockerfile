# ==============================================================================
# Multi-Stage Production Dockerfile for Insurance Claims Processing System
# Using uv for deterministic, reproducible dependency resolution and installation
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Builder
# ------------------------------------------------------------------------------
FROM python:3.12-slim AS builder

# Install uv from official binary distribution
COPY --from=ghcr.io/astral-sh/uv:0.6.5 /uv /bin/uv

# Compile bytecode during build for fast startup
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install build dependencies required for compiling C extensions (if any)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy packaging configuration and lockfile
COPY pyproject.toml uv.lock ./

# Install production dependencies only into /app/.venv
RUN uv sync --frozen --no-dev --no-cache

# ------------------------------------------------------------------------------
# Stage 2: Runtime
# ------------------------------------------------------------------------------
FROM python:3.12-slim

# Install minimal runtime shared libraries and curl for health check
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Create dedicated non-root application user and group (UID/GID 1000)
RUN groupadd -r -g 1000 appuser && \
    useradd -r -u 1000 -g appuser -d /app -s /sbin/nologin appuser

# Set runtime environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app

WORKDIR /app

# Copy pre-built virtual environment from builder stage
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv

# Copy application source code and seed assets
COPY --chown=appuser:appuser . /app

# Switch to unprivileged non-root user
USER appuser

# Expose FastAPI application port
EXPOSE 8000

# Container health probe checking live application status
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Production server entrypoint
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
