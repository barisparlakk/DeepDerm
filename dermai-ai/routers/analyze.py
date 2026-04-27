"""
analyze.py
==========
FastAPI router providing:
  POST /analyze  — receive image, run YOLO11, persist result, return JSON
  GET  /results/{photo_id} — retrieve stored analysis from DB
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from clinical.postprocess import build_clinical_result, compare_clinical_results
from db.database import get_db
from db.models import AiAnalizSonuclari
from models.detector import detector
from quality.image_quality import assess_image_quality
from utils.image_utils import (
    decode_image_to_bgr,
    draw_detections,
    encode_image_to_jpeg,
    preprocess_image,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Storage directory for annotated images
STORAGE_DIR = Path(os.getenv("STORAGE_DIR", "storage/annotated"))
STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def _serialize_result(row: AiAnalizSonuclari) -> dict:
    return {
        "id":                   str(row.id),
        "photo_id":             str(row.photo_id),
        "patient_id":           str(row.patient_id),
        "detections":           row.detections,
        "counts":               row.counts,
        "severity":             row.severity,
        "quality":              row.quality,
        "total_lesion_count":   row.total_lesion_count,
        "inflammatory_total":   row.inflammatory_total,
        "weighted_score":       row.weighted_score,
        "clinical_summary":     row.clinical_summary,
        "annotated_image_url":  row.annotated_image_url,
        "model_version":        row.model_version,
        "analyzed_at":          row.analyzed_at.isoformat() if row.analyzed_at else None,
    }


# ── POST /analyze ─────────────────────────────────────────────────────────────

@router.post("/analyze")
async def analyze_photo(
    photo_id:   str        = Form(..., description="UUID of the photo record"),
    patient_id: str        = Form(..., description="UUID of the patient"),
    image:      UploadFile = File(..., description="Face photo file"),
    db:         AsyncSession = Depends(get_db),
):
    """
    Full analysis pipeline:
    1. Decode & preprocess image (640×640 RGB float32)
    2. Run YOLO11 inference
    3. Draw bounding boxes on a BGR copy
    4. Save annotated JPEG to storage/annotated/{photo_id}.jpg
    5. Persist result to ai_analiz_sonuclari
    6. Return JSON response
    """
    # ── Validate UUIDs ────────────────────────────────────────────────────────
    try:
        photo_uuid   = uuid.UUID(photo_id)
        patient_uuid = uuid.UUID(patient_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="photo_id and patient_id must be valid UUIDs")

    # ── Read image bytes ──────────────────────────────────────────────────────
    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty image file received")

    # ── Quality control ───────────────────────────────────────────────────────
    try:
        quality = assess_image_quality(image_bytes)
    except Exception as exc:
        logger.exception("Image quality check failed")
        raise HTTPException(status_code=400, detail=f"Cannot assess image quality: {exc}") from exc

    # ── Preprocess for inference ──────────────────────────────────────────────
    try:
        preprocessed = preprocess_image(image_bytes)
        bgr_img      = decode_image_to_bgr(image_bytes)
    except Exception as exc:
        logger.exception("Image decode failed")
        raise HTTPException(status_code=400, detail=f"Cannot decode image: {exc}") from exc

    # ── YOLO11 inference ──────────────────────────────────────────────────────
    try:
        detections = detector.detect(preprocessed)
    except Exception as exc:
        logger.exception("Inference failed")
        raise HTTPException(status_code=500, detail=f"Inference error: {exc}") from exc

    # ── Draw bounding boxes ───────────────────────────────────────────────────
    annotated_bgr = draw_detections(bgr_img, detections)

    # ── Save annotated image ──────────────────────────────────────────────────
    annotated_filename = f"{photo_id}.jpg"
    annotated_path     = STORAGE_DIR / annotated_filename
    try:
        jpeg_bytes = encode_image_to_jpeg(annotated_bgr)
        annotated_path.write_bytes(jpeg_bytes)
    except Exception as exc:
        logger.exception("Failed to save annotated image")
        raise HTTPException(status_code=500, detail=f"Storage error: {exc}") from exc

    annotated_image_url = f"/storage/annotated/{annotated_filename}"

    # ── Strip class_id from public detections (internal field) ────────────────
    public_detections = [
        {
            "label":      d["label"],
            "label_en":   d["label_en"],
            "confidence": d["confidence"],
            "bbox":       d["bbox"],
        }
        for d in detections
    ]

    clinical = build_clinical_result(public_detections, quality)

    analyzed_at = datetime.now(timezone.utc)

    # ── Persist to DB ─────────────────────────────────────────────────────────
    row = AiAnalizSonuclari(
        id                  = uuid.uuid4(),
        photo_id            = photo_uuid,
        patient_id          = patient_uuid,
        detections          = public_detections,
        total_lesion_count  = len(public_detections),
        counts              = clinical["counts"],
        severity            = clinical["severity"],
        quality             = quality,
        inflammatory_total  = clinical["inflammatory_total"],
        weighted_score      = clinical["weighted_score"],
        clinical_summary    = clinical["clinical_summary"],
        annotated_image_url = annotated_image_url,
        model_version       = detector.version,
        analyzed_at         = analyzed_at,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)

    logger.info(
        "Analyzed photo %s: %d detections saved (model=%s)",
        photo_id, len(public_detections), detector.version,
    )

    return {
        "photo_id":             photo_id,
        "patient_id":           patient_id,
        "detections":           public_detections,
        "counts":               clinical["counts"],
        "severity":             clinical["severity"],
        "quality":              quality,
        "total_lesion_count":   len(public_detections),
        "inflammatory_total":   clinical["inflammatory_total"],
        "weighted_score":       clinical["weighted_score"],
        "clinical_summary":     clinical["clinical_summary"],
        "annotated_image_url":  annotated_image_url,
        "model_version":        detector.version,
        "analyzed_at":          analyzed_at.isoformat(),
    }


# ── GET /results/{photo_id} ───────────────────────────────────────────────────

@router.get("/results/{photo_id}")
async def get_results(
    photo_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Return the latest analysis result for a given photo UUID.
    Raises 404 if no analysis has been run for this photo.
    """
    try:
        photo_uuid = uuid.UUID(photo_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="photo_id must be a valid UUID")

    stmt = (
        select(AiAnalizSonuclari)
        .where(AiAnalizSonuclari.photo_id == photo_uuid)
        .order_by(AiAnalizSonuclari.analyzed_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    row: AiAnalizSonuclari | None = result.scalar_one_or_none()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"No analysis found for photo_id={photo_id}",
        )

    return _serialize_result(row)


# ── GET /results/patient/{patient_id}/timeline ────────────────────────────────

@router.get("/results/patient/{patient_id}/timeline")
async def get_patient_timeline(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Return all stored AI analysis results for a patient, newest first.
    Used by the doctor panel for follow-up charts.
    """
    try:
        patient_uuid = uuid.UUID(patient_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="patient_id must be a valid UUID")

    stmt = (
        select(AiAnalizSonuclari)
        .where(AiAnalizSonuclari.patient_id == patient_uuid)
        .order_by(AiAnalizSonuclari.analyzed_at.desc())
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()

    return {
        "patient_id": patient_id,
        "results": [_serialize_result(row) for row in rows],
    }


# ── GET /compare ──────────────────────────────────────────────────────────────

@router.get("/compare")
async def compare_results(
    previous_photo_id: str,
    current_photo_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Compare two analyzed photos and return T1-T2 clinical trend.
    """
    try:
        previous_uuid = uuid.UUID(previous_photo_id)
        current_uuid = uuid.UUID(current_photo_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="photo IDs must be valid UUIDs")

    async def latest_for_photo(photo_uuid: uuid.UUID) -> AiAnalizSonuclari | None:
        stmt = (
            select(AiAnalizSonuclari)
            .where(AiAnalizSonuclari.photo_id == photo_uuid)
            .order_by(AiAnalizSonuclari.analyzed_at.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    previous = await latest_for_photo(previous_uuid)
    current = await latest_for_photo(current_uuid)

    if previous is None or current is None:
        raise HTTPException(status_code=404, detail="Both photos must have AI analysis results")
    if previous.patient_id != current.patient_id:
        raise HTTPException(status_code=400, detail="Photos belong to different patients")

    comparison = compare_clinical_results(_serialize_result(previous), _serialize_result(current))

    return {
        "patient_id": str(current.patient_id),
        "previous": _serialize_result(previous),
        "current": _serialize_result(current),
        "comparison": comparison,
    }
