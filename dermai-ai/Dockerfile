# ─────────────────────────────────────────────────────────────────────────────
# DermAI FastAPI Microservice — Dockerfile
# ─────────────────────────────────────────────────────────────────────────────
# Multi-stage: keeps the final image lean by separating dependency install.
# Base: python:3.11-slim (Debian)
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.11-slim AS builder

WORKDIR /build

# System deps needed to compile some Python packages (opencv, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender1 \
        libgomp1 \
        gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps into a separate prefix so we can copy cleanly
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --prefix=/install --no-cache-dir -r requirements.txt

# ── Final image ───────────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder stage
COPY --from=builder /install /usr/local

# Runtime system libraries (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender1 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy application code
COPY . .

# Pre-download yolov8n.pt so it's baked into the image
# (avoids network fetch on first inference in production)
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"

# Create storage directory
RUN mkdir -p storage/annotated

# Expose FastAPI port
EXPOSE 8000

# ── Environment defaults (override via docker-compose / k8s env) ──────────────
ENV DEEPDERM_DB_URL="postgresql+asyncpg://postgres:postgres@db:5432/deepderm" \
    DERMAI_MODEL_PATH="yolov8n.pt" \
    DERMAI_MODEL_VERSION="yolov8n-v1-demo" \
    DERMAI_CONF_THRESHOLD="0.25" \
    CORS_ORIGINS="http://localhost:8080,http://localhost:5173" \
    STORAGE_DIR="storage/annotated"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
