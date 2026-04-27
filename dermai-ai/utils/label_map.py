"""
label_map.py
============
Bidirectional mapping between English and Turkish acne lesion class names.
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


def _normalize_label(label: str) -> str:
    """Normalize label names for resilient matching."""
    return " ".join(label.strip().lower().replace("_", " ").replace("-", " ").split())


EN_NORMALIZED_TO_TR: dict[str, str] = {
    _normalize_label(en): tr
    for en, tr in EN_TO_TR.items()
}


def to_turkish_label(label_en: str) -> str:
    """
    Map an English label to Turkish when it is one of the known acne classes.
    Falls back to the original label for unknown classes.
    """
    return EN_NORMALIZED_TO_TR.get(_normalize_label(label_en), label_en)
