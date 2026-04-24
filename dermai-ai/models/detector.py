"""
detector.py
===========
YOLOv8 inference wrapper for acne lesion detection.
"""
from __future__ import annotations

import os
import logging
import numpy as np
from ultralytics import YOLO

from utils.label_map import ID_TO_EN, to_turkish_label
from models.heuristic_detector import detect_heuristic_lesions

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────
DEFAULT_MODEL   = "yolov8n.pt"                      # downloaded automatically
MODEL_PATH      = os.getenv("DERMAI_MODEL_PATH", DEFAULT_MODEL)
MODEL_VERSION   = os.getenv("DERMAI_MODEL_VERSION", os.path.splitext(os.path.basename(MODEL_PATH))[0])
CONFIDENCE_THRESHOLD = float(os.getenv("DERMAI_CONF_THRESHOLD", "0.25"))
IOU_THRESHOLD        = float(os.getenv("DERMAI_IOU_THRESHOLD",  "0.45"))
HEURISTIC_FALLBACK   = os.getenv("DERMAI_HEURISTIC_FALLBACK", "true").lower() == "true"

HEURISTIC_VERSION = "heuristic-acne-v1"


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
        if MODEL_PATH == DEFAULT_MODEL:
            if HEURISTIC_FALLBACK:
                logger.warning(
                    "Using default yolov8n.pt (COCO classes). "
                    "Heuristic acne fallback is enabled. "
                    "Set DERMAI_MODEL_PATH to acne-trained weights for better lesion detection."
                )
            else:
                logger.warning(
                    "Using default yolov8n.pt (COCO classes). "
                    "Set DERMAI_MODEL_PATH to acne-trained weights for clinical lesion detection."
                )
        self._model = YOLO(MODEL_PATH)
        self._model_names = getattr(self._model, "names", {})
        self._loaded = True
        logger.info("Model '%s' loaded from '%s'", MODEL_VERSION, MODEL_PATH)

    def _use_heuristic_fallback(self) -> bool:
        """Use image-based fallback when acne-specific weights are unavailable."""
        return MODEL_PATH == DEFAULT_MODEL and HEURISTIC_FALLBACK

    def _resolve_label_en(self, class_id: int) -> str:
        """Resolve class_id to model-native label text."""
        names = getattr(self, "_model_names", {})

        label: str | None = None
        if isinstance(names, dict):
            raw = names.get(class_id)
            if raw is not None:
                label = str(raw).strip()
        elif isinstance(names, (list, tuple)) and 0 <= class_id < len(names):
            label = str(names[class_id]).strip()

        if label:
            return label
        return ID_TO_EN.get(class_id, f"class_{class_id}")

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

        if self._use_heuristic_fallback():
            return detect_heuristic_lesions(image_np=image_np, conf_threshold=CONFIDENCE_THRESHOLD)

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

                label_en = self._resolve_label_en(coco_class_id)
                label_tr = to_turkish_label(label_en)

                detections.append({
                    "label":      label_tr,
                    "label_en":   label_en,
                    "confidence": conf,
                    "class_id":   coco_class_id,
                    "bbox":       bbox,
                })

        detections.sort(key=lambda d: d["confidence"], reverse=True)

        return detections

    @property
    def version(self) -> str:
        if self._use_heuristic_fallback():
            return f"{MODEL_VERSION}+{HEURISTIC_VERSION}"
        return MODEL_VERSION


# Module-level singleton used by routers
detector = AcneDetector()
