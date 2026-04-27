"""
heuristic_detector.py
=====================
Rule-based lesion candidate detector used when acne-trained YOLO weights
are not available.

This module is intentionally deterministic and image-driven (no random values).
It detects candidate regions using skin masking + redness/darkness contrasts.
"""
from __future__ import annotations

import cv2
import numpy as np

from utils.label_map import ID_TO_EN, to_turkish_label

EN_TO_ID: dict[str, int] = {label: idx for idx, label in ID_TO_EN.items()}


def _as_uint8_rgb(image_np: np.ndarray) -> np.ndarray:
    if image_np.dtype == np.uint8:
        return image_np
    clipped = np.clip(image_np, 0.0, 1.0)
    return (clipped * 255.0).astype(np.uint8)


def _build_skin_mask(bgr: np.ndarray) -> np.ndarray:
    """Approximate skin mask in YCrCb space (works reasonably for many tones)."""
    ycrcb = cv2.cvtColor(bgr, cv2.COLOR_BGR2YCrCb)
    lower = np.array([0, 133, 77], dtype=np.uint8)
    upper = np.array([255, 173, 127], dtype=np.uint8)
    mask = cv2.inRange(ycrcb, lower, upper)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
    return mask


def _bbox_iou(a: dict, b: dict) -> float:
    ax1, ay1 = a["x"], a["y"]
    ax2, ay2 = ax1 + a["w"], ay1 + a["h"]
    bx1, by1 = b["x"], b["y"]
    bx2, by2 = bx1 + b["w"], by1 + b["h"]

    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = float(iw * ih)
    if inter <= 0:
        return 0.0

    area_a = float(max(1, a["w"]) * max(1, a["h"]))
    area_b = float(max(1, b["w"]) * max(1, b["h"]))
    return inter / max(1e-6, (area_a + area_b - inter))


def _nms(detections: list[dict], iou_threshold: float = 0.30, max_keep: int = 25) -> list[dict]:
    kept: list[dict] = []
    for det in detections:
        if all(_bbox_iou(det["bbox"], k["bbox"]) < iou_threshold for k in kept):
            kept.append(det)
            if len(kept) >= max_keep:
                break
    return kept


def _classify_candidate(area: float, mean_redness: float, mean_darkness: float) -> str:
    # Conservative label heuristics until trained weights are available.
    if mean_redness >= 0.11:
        if area >= 1200:
            return "Nodule"
        if area >= 450:
            return "Pustule"
        if area >= 140:
            return "Papule"
        return "Inflammatory lesion"

    if mean_darkness >= 0.055:
        return "Comedone"

    if area >= 1600:
        return "Cyst"

    return "Papule"


def _confidence(mean_redness: float, mean_darkness: float, area: float, area_norm: float) -> float:
    red_score = np.clip((mean_redness + 0.02) / 0.20, 0.0, 1.0)
    dark_score = np.clip((mean_darkness + 0.015) / 0.15, 0.0, 1.0)
    size_score = np.clip(area / max(1.0, area_norm), 0.0, 1.0)

    score = 0.20 + 0.45 * max(red_score, dark_score) + 0.35 * size_score
    return float(np.clip(score, 0.20, 0.95))


def detect_heuristic_lesions(image_np: np.ndarray, conf_threshold: float = 0.25) -> list[dict]:
    """
    Return acne-like lesion candidates from a face image using deterministic CV.
    Output schema matches the main YOLO detector output.
    """
    rgb = _as_uint8_rgb(image_np)
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

    skin_mask = _build_skin_mask(bgr)
    skin_bool = skin_mask > 0

    # If skin area is tiny, return no detections instead of guessing.
    if int(np.count_nonzero(skin_bool)) < 3500:
        return []

    rgb_f = rgb.astype(np.float32) / 255.0
    r = rgb_f[:, :, 0]
    g = rgb_f[:, :, 1]
    b = rgb_f[:, :, 2]

    redness = r - 0.5 * (g + b)

    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0
    local_bg = cv2.GaussianBlur(gray, (21, 21), 0)
    darkness = local_bg - gray

    red_vals = redness[skin_bool]
    dark_vals = darkness[skin_bool]

    red_threshold = max(0.045, float(red_vals.mean() + 0.75 * red_vals.std()))
    dark_threshold = max(0.035, float(dark_vals.mean() + 0.80 * dark_vals.std()))

    red_mask = ((redness > red_threshold) & skin_bool).astype(np.uint8) * 255
    dark_mask = ((darkness > dark_threshold) & skin_bool).astype(np.uint8) * 255

    candidate_mask = cv2.bitwise_or(red_mask, dark_mask)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    candidate_mask = cv2.morphologyEx(candidate_mask, cv2.MORPH_OPEN, kernel, iterations=1)
    candidate_mask = cv2.dilate(candidate_mask, kernel, iterations=1)

    contours, _ = cv2.findContours(candidate_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    h, w = rgb.shape[:2]
    img_area = float(h * w)
    min_area = max(26.0, img_area * 0.00006)
    max_area = img_area * 0.015
    area_norm = img_area * 0.004
    effective_conf_threshold = max(conf_threshold, 0.55)

    detections: list[dict] = []

    for cnt in contours:
        area = float(cv2.contourArea(cnt))
        if area < min_area or area > max_area:
            continue

        x, y, bw, bh = cv2.boundingRect(cnt)
        if bw < 4 or bh < 4:
            continue

        aspect = max(bw, bh) / max(1.0, min(bw, bh))
        if aspect > 2.5:
            continue

        cnt_mask = np.zeros(candidate_mask.shape, dtype=np.uint8)
        cv2.drawContours(cnt_mask, [cnt], -1, 255, thickness=cv2.FILLED)
        roi = cnt_mask > 0

        mean_redness = float(np.mean(redness[roi])) if np.any(roi) else 0.0
        mean_darkness = float(np.mean(darkness[roi])) if np.any(roi) else 0.0
        if mean_redness < (red_threshold * 0.85) and mean_darkness < (dark_threshold * 0.85):
            continue

        label_en = _classify_candidate(area=area, mean_redness=mean_redness, mean_darkness=mean_darkness)
        conf = _confidence(
            mean_redness=mean_redness,
            mean_darkness=mean_darkness,
            area=area,
            area_norm=area_norm,
        )
        if conf < effective_conf_threshold:
            continue

        label_tr = to_turkish_label(label_en)
        class_id = EN_TO_ID.get(label_en, -1)

        detections.append(
            {
                "label": label_tr,
                "label_en": label_en,
                "confidence": round(conf, 4),
                "class_id": class_id,
                "bbox": {"x": int(x), "y": int(y), "w": int(bw), "h": int(bh)},
            }
        )

    detections.sort(key=lambda d: d["confidence"], reverse=True)
    return _nms(detections, iou_threshold=0.30, max_keep=25)
