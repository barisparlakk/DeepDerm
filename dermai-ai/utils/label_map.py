"""
label_map.py
============
Bidirectional mapping between English and Turkish acne lesion class names.
"""

# Canonical API labels. The trained DermAI dataset uses lowercase/plural names
# such as "papules"; normalize them before exposing results to the app.
LABELS_EN: list[str] = [
    "Comedone",
    "Nodule",
    "Papule",
    "Pustule",
    "Cyst",
    "Inflammatory lesion",
    "Scar",
]

# Turkish display names shown in the doctor panel and API responses
LABELS_TR: list[str] = [
    "Komedon",
    "Nodül",
    "Papül",
    "Püstül",
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

EN_ALIASES: dict[str, str] = {
    "comedone": "Comedone",
    "comedones": "Comedone",
    "blackhead": "Comedone",
    "blackheads": "Comedone",
    "whitehead": "Comedone",
    "whiteheads": "Comedone",
    "nodule": "Nodule",
    "nodules": "Nodule",
    "papule": "Papule",
    "papules": "Papule",
    "pustule": "Pustule",
    "pustules": "Pustule",
    "cyst": "Cyst",
    "cysts": "Cyst",
    "inflammatory lesion": "Inflammatory lesion",
    "inflammatory lesions": "Inflammatory lesion",
    "scar": "Scar",
    "scars": "Scar",
}


def canonical_label_en(label_en: str) -> str:
    """Return the canonical English API label for model-native class names."""
    return EN_ALIASES.get(_normalize_label(label_en), label_en)


def to_turkish_label(label_en: str) -> str:
    """
    Map an English label to Turkish when it is one of the known acne classes.
    Falls back to the original label for unknown classes.
    """
    canonical = canonical_label_en(label_en)
    return EN_NORMALIZED_TO_TR.get(_normalize_label(canonical), canonical)
