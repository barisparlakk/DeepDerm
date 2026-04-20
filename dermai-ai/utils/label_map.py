"""
label_map.py
============
Bidirectional mapping between English and Turkish acne lesion class names.

Phase 1: 7 acne/skin finding classes targeted by the DermAI detector.
When fine-tuned weights arrive, training labels should match LABELS_EN exactly.
"""

# Ordered list — index matches the custom-trained YOLO class ID
LABELS_EN: list[str] = [
    "Papule",
    "Pustule",
    "Nodule",
    "Comedone",
    "Cyst",
    "Inflammatory lesion",
    "Scar",
]

# Turkish display names shown in the doctor panel and API responses
LABELS_TR: list[str] = [
    "Papül",
    "Püstül",
    "Nodül",
    "Komedon",
    "Kist",
    "İnflamatuar lezyon",
    "Skar / Akne izi",
]

# Lookup dictionaries
EN_TO_TR: dict[str, str] = dict(zip(LABELS_EN, LABELS_TR))
TR_TO_EN: dict[str, str] = dict(zip(LABELS_TR, LABELS_EN))

# Index-based lookup (used when model returns class_id integers)
ID_TO_EN: dict[int, str] = dict(enumerate(LABELS_EN))
ID_TO_TR: dict[int, str] = dict(enumerate(LABELS_TR))

# ── COCO demo mapping ─────────────────────────────────────────────────────────
# NOTE: yolov8n.pt is trained on 80 COCO classes (people, chairs, cars …).
# We do NOT have acne-labeled weights yet.  Until fine-tuned weights are ready
# this demo map cycles detected COCO class IDs onto acne labels so the pipeline
# can be tested end-to-end with real images.
# REMOVE this mapping and use ID_TO_TR directly once real weights are in place.
NUM_ACNE_CLASSES = len(LABELS_EN)

def coco_class_to_acne_label(coco_class_id: int) -> tuple[str, str]:
    """
    Maps a COCO class integer → (label_en, label_tr).
    Uses modulo so every possible COCO class gets a deterministic acne label.
    This is intentionally naive — replace with direct ID_TO_EN lookup when
    fine-tuned weights become available.
    """
    acne_id = coco_class_id % NUM_ACNE_CLASSES
    return ID_TO_EN[acne_id], ID_TO_TR[acne_id]
