"""
main.py
=======
DermAI FastAPI application entry point.

Endpoints:
  GET  /health            — liveness probe (Spring Boot uses this)
  POST /analyze           — full analysis pipeline
  GET  /results/{photo_id}— retrieve stored results
  GET  /storage/annotated/{filename} — serve annotated images (static files)
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()  # load .env file if present

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from models.detector import detector
from routers.analyze import router as analyze_router

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("dermai-ai")

STORAGE_DIR = Path(os.getenv("STORAGE_DIR", "storage/annotated"))
STORAGE_DIR.mkdir(parents=True, exist_ok=True)


# ── Lifespan — pre-load model to avoid cold-start on first request ────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("DermAI service starting — loading YOLO model …")
    detector.load()
    logger.info("Model ready. Service is up.")
    yield
    logger.info("DermAI service shutting down.")


# ── App factory ───────────────────────────────────────────────────────────────
app = FastAPI(
    title       = "DermAI — Acne Detection Microservice",
    description = (
        "FastAPI service that runs YOLO11 acne lesion detection on face photos "
        "uploaded through the DeepDerm patient app. Called by the Spring Boot backend."
    ),
    version     = "1.0.0",
    docs_url    = "/docs",
    redoc_url   = "/redoc",
    lifespan    = lifespan,
)

# ── CORS (Spring Boot backend + dev frontend) ─────────────────────────────────
_allowed_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:8080,http://localhost:5173,http://localhost:3000",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins     = _allowed_origins,
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

# ── Static files — annotated images ──────────────────────────────────────────
app.mount(
    "/storage/annotated",
    StaticFiles(directory=str(STORAGE_DIR)),
    name="annotated",
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(analyze_router, tags=["Analysis"])


# ── Health endpoint ───────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
async def health():
    """
    Liveness probe consumed by Spring Boot AiAnalysisService.
    Returns 200 + status info when the service is ready.
    """
    return {
        "status":        "ok",
        "service":       "dermai-ai",
        "model_version": detector.version,
        "model_loaded":  detector._loaded,
    }
