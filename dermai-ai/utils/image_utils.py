"""
image_utils.py
==============
Image preprocessing pipeline and bounding-box annotation helpers.
"""
from __future__ import annotations

import io
import cv2
import numpy as np
from PIL import Image

# ── Palette — one distinct colour per acne class ──────────────────────────────
_CLASS_COLORS: list[tuple[int, int, int]] = [
    (255, 99,  99),   # Papule        — red-ish
    (255, 190,  50),  # Pustule       — amber
    (100, 180, 255),  # Nodule        — sky blue
    (80,  200, 120),  # Comedone      — green
    (200,  80, 255),  # Cyst          — purple
    (255, 140,   0),  # Inflammatory  — orange
    (160, 160, 160),  # Scar          — grey
]

TARGET_SIZE = 640  # YOLOv8 default input size


def preprocess_image(image_bytes: bytes) -> np.ndarray:
    """
    Convert raw image bytes → RGB numpy array (H×W×3, float32, values in [0,1]).
    Steps:
      1. Decode via Pillow (handles JPEG, PNG, WEBP …)
      2. Convert to RGB (drops alpha if present)
      3. Resize to TARGET_SIZE × TARGET_SIZE
      4. Normalize to [0, 1]
    """
    pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    pil_img = pil_img.resize((TARGET_SIZE, TARGET_SIZE), Image.LANCZOS)
    arr = np.array(pil_img, dtype=np.float32) / 255.0
    return arr


def decode_image_to_bgr(image_bytes: bytes) -> np.ndarray:
    """
    Decode raw image bytes to uint8 BGR numpy array (for OpenCV drawing).
    Resizes to TARGET_SIZE × TARGET_SIZE.
    """
    pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    pil_img = pil_img.resize((TARGET_SIZE, TARGET_SIZE), Image.LANCZOS)
    bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    return bgr


def draw_detections(bgr_image: np.ndarray, detections: list[dict]) -> np.ndarray:
    """
    Draw coloured bounding boxes and label overlays onto a BGR image copy.

    Each detection dict is expected to have:
      label_en  : str   (English label — used to pick colour)
      label     : str   (Turkish label — shown on image)
      confidence: float
      bbox      : dict with keys x, y, w, h  (pixel coords in TARGET_SIZE space)
      class_id  : int   (optional; used for colour when label_en not matched)
    """
    from utils.label_map import LABELS_EN

    img = bgr_image.copy()

    for det in detections:
        bbox      = det["bbox"]
        x, y, w, h = int(bbox["x"]), int(bbox["y"]), int(bbox["w"]), int(bbox["h"])
        label_tr  = det.get("label", "")
        label_en  = det.get("label_en", "")
        conf      = det.get("confidence", 0.0)
        class_id  = det.get("class_id", 0) % len(_CLASS_COLORS)

        # Pick colour by English label index (falls back to class_id)
        try:
            color_idx = LABELS_EN.index(label_en) % len(_CLASS_COLORS)
        except ValueError:
            color_idx = class_id % len(_CLASS_COLORS)

        color = _CLASS_COLORS[color_idx]   # RGB
        bgr_color = (color[2], color[1], color[0])  # → BGR for OpenCV

        # Bounding box
        cv2.rectangle(img, (x, y), (x + w, y + h), bgr_color, 2)

        # Label background pill
        text     = f"{label_tr} {conf:.0%}"
        font     = cv2.FONT_HERSHEY_SIMPLEX
        scale    = 0.45
        thickness = 1
        (tw, th), baseline = cv2.getTextSize(text, font, scale, thickness)
        pad = 4
        cv2.rectangle(img,
                      (x, y - th - pad * 2 - baseline),
                      (x + tw + pad * 2, y),
                      bgr_color, cv2.FILLED)
        cv2.putText(img, text,
                    (x + pad, y - baseline - pad),
                    font, scale, (255, 255, 255), thickness, cv2.LINE_AA)

    return img


def encode_image_to_jpeg(bgr_image: np.ndarray, quality: int = 90) -> bytes:
    """Encode a BGR numpy array to JPEG bytes."""
    ok, buf = cv2.imencode(".jpg", bgr_image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError("Failed to encode annotated image to JPEG")
    return buf.tobytes()
