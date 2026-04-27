"""
image_quality.py
================
Lightweight image quality control for acne follow-up photos.

The goal is not to reject every imperfect photo. It gives the clinical pipeline
structured warnings so low-quality inputs can be shown as "needs retake/review"
instead of silently producing overconfident AI output.
"""
from __future__ import annotations

import io

import cv2
import numpy as np
from PIL import Image


def _skin_mask_coverage(bgr: np.ndarray) -> float:
    ycrcb = cv2.cvtColor(bgr, cv2.COLOR_BGR2YCrCb)
    lower = np.array([0, 133, 77], dtype=np.uint8)
    upper = np.array([255, 173, 127], dtype=np.uint8)
    mask = cv2.inRange(ycrcb, lower, upper)
    return float(np.count_nonzero(mask) / max(1, mask.size))


def assess_image_quality(image_bytes: bytes) -> dict:
    """
    Return deterministic quality metrics and flags for an uploaded image.

    Output schema:
        {
          "quality_passed": bool,
          "quality_score": float,
          "flags": ["low_light", ...],
          "metrics": {...}
        }
    """
    pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    width, height = pil_img.size

    rgb = np.array(pil_img)
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

    brightness = float(gray.mean() / 255.0)
    contrast = float(gray.std() / 255.0)
    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    skin_coverage = _skin_mask_coverage(bgr)
    min_side = min(width, height)

    flags: list[str] = []
    penalties = 0.0

    if min_side < 480:
        flags.append("low_resolution")
        penalties += 0.22
    if brightness < 0.22:
        flags.append("low_light")
        penalties += 0.20
    elif brightness > 0.88:
        flags.append("overexposed")
        penalties += 0.20
    if contrast < 0.10:
        flags.append("low_contrast")
        penalties += 0.14
    if blur_score < 55.0:
        flags.append("blurred")
        penalties += 0.22
    if skin_coverage < 0.10:
        flags.append("low_skin_coverage")
        penalties += 0.22

    quality_score = round(float(np.clip(1.0 - penalties, 0.0, 1.0)), 4)

    return {
        "quality_passed": quality_score >= 0.60,
        "quality_score": quality_score,
        "flags": flags,
        "metrics": {
            "width": int(width),
            "height": int(height),
            "brightness": round(brightness, 4),
            "contrast": round(contrast, 4),
            "blur_score": round(blur_score, 2),
            "skin_coverage": round(skin_coverage, 4),
        },
    }

