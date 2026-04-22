"""
detector.py
===========
YOLOv8 inference wrapper for acne lesion detection.

Phase 1 — DEMO MODE
-------------------
We load the stock yolov8n.pt (COCO-pretrained) because no acne-specific
weights exist yet.  The COCO class IDs are mapped onto acne labels via
utils.label_map.coco_class_to_acne_label() for end-to-end pipeline testing.

Phase 2 — Production
--------------------
Set the MODEL_PATH env var (or DERMAI_MODEL_PATH) to point at the fine-tuned
.pt file.  id_to_label() will then map class IDs directly (0→Papule, 1→Pustule …)
using utils.label_map.ID_TO_EN.  No other code changes needed.
"""
from __future__ import annotations

import os
import logging
import numpy as np
from ultralytics import YOLO

from utils.label_map import coco_class_to_acne_label, ID_TO_EN, ID_TO_TR

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────
DEFAULT_MODEL   = "yolov8n.pt"                      # downloaded automatically
MODEL_PATH      = os.getenv("DERMAI_MODEL_PATH", DEFAULT_MODEL)
MODEL_VERSION   = os.getenv("DERMAI_MODEL_VERSION", "yolov8n-v1-demo")
CONFIDENCE_THRESHOLD = float(os.getenv("DERMAI_CONF_THRESHOLD", "0.25"))
IOU_THRESHOLD        = float(os.getenv("DERMAI_IOU_THRESHOLD",  "0.45"))

# Fine-tuned mode: set this to True when real acne weights are loaded.
# When False → COCO class IDs are remapped (demo/testing).
FINE_TUNED = MODEL_PATH != DEFAULT_MODEL


class AcneDetector:
    """
    Singleton-style wrapper around a YOLO model.

    Usage::

        detector = AcneDetector()
        results = detector.detect(preprocessed_np_array)

    Returns a list of detection dicts ready for the API response.
    """

    _instance: "AcneDetector | None" = None

    def __new__(cls) -> "AcneDetector":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    def load(self) -> None:
        if self._loaded:
            return
        logger.info("Loading YOLO model from: %s", MODEL_PATH)
        self._model = YOLO(MODEL_PATH)
        self._loaded = True
        logger.info("Model '%s' loaded (fine_tuned=%s)", MODEL_VERSION, FINE_TUNED)

    # ── Inference ─────────────────────────────────────────────────────────────

    def detect(self, image_np: np.ndarray) -> list[dict]:
        """
        Run inference on a preprocessed RGB float32 image (H×W×3, values 0‥1).

        Returns a list of dicts::

            {
                "label":      "Papül",       # Turkish
                "label_en":   "Papule",      # English
                "confidence": 0.87,
                "class_id":   0,
                "bbox": {"x": 120, "y": 340, "w": 45, "h": 50}
            }
        """
        if not self._loaded:
            self.load()

        # Ultralytics accepts numpy arrays natively (RGB uint8 or float)
        results = self._model.predict(
            source        = image_np,
            conf          = CONFIDENCE_THRESHOLD,
            iou           = IOU_THRESHOLD,
            verbose       = False,
        )

        detections: list[dict] = []
        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                coco_class_id = int(box.cls.item())
                conf          = round(float(box.conf.item()), 4)

                # x1 y1 x2 y2 → x y w h
                x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
                bbox = {"x": x1, "y": y1, "w": x2 - x1, "h": y2 - y1}

                if FINE_TUNED:
                    label_en = ID_TO_EN.get(coco_class_id, "Unknown")
                    label_tr = ID_TO_TR.get(coco_class_id, "Bilinmeyen")
                else:
                    label_en, label_tr = coco_class_to_acne_label(coco_class_id)

                detections.append({
                    "label":      label_tr,
                    "label_en":   label_en,
                    "confidence": conf,
                    "class_id":   coco_class_id,
                    "bbox":       bbox,
                })

        # --- DEMO MOCK ANNOTATIONS ---
        # If we are in DEMO mode and no objects (like a person) were confidently found,
        # let's generate 3-5 realistic looking fake lesions so the doctor panel UI can be tested!
        if not FINE_TUNED and len(detections) == 0:
            import random
            num_mock_lesions = random.randint(2, 5)
            h, w = image_np.shape[:2]
            
            for _ in range(num_mock_lesions):
                # Randomize class
                fake_class_id = random.randint(0, len(ID_TO_EN) - 1)
                label_en = ID_TO_EN[fake_class_id]
                label_tr = ID_TO_TR[fake_class_id]
                
                # Randomize box near center of image
                cx = random.randint(int(w * 0.25), int(w * 0.75))
                cy = random.randint(int(h * 0.25), int(h * 0.75))
                bw = random.randint(30, 80)
                bh = random.randint(30, 80)
                
                bbox = {
                    "x": max(0, cx - bw//2),
                    "y": max(0, cy - bh//2),
                    "w": bw,
                    "h": bh
                }
                
                detections.append({
                    "label": label_tr,
                    "label_en": label_en,
                    "confidence": round(random.uniform(0.65, 0.95), 2),
                    "class_id": fake_class_id,
                    "bbox": bbox,
                })

        return detections

    @property
    def version(self) -> str:
        return MODEL_VERSION


# Module-level singleton used by routers
detector = AcneDetector()
