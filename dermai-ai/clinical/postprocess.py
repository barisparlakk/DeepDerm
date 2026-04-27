"""
postprocess.py
==============
Clinical interpretation layer for raw acne detections.

This module converts model output into the fields the doctor panel actually
needs: class-wise counts, Hayashi severity, weighted trend scores, and T1-T2
comparison summaries.
"""
from __future__ import annotations

from copy import deepcopy


COUNT_KEYS = ("papule", "pustule", "nodule", "comedone")
DISPLAY_TR = {
    "papule": "Papül",
    "pustule": "Püstül",
    "nodule": "Nodül",
    "comedone": "Komedon",
}
WEIGHTS = {
    "papule": 1.0,
    "pustule": 2.0,
    "nodule": 3.0,
    "comedone": 0.25,
}


def _normalize_label(label: str | None) -> str:
    if not label:
        return ""
    value = " ".join(label.strip().lower().replace("_", " ").replace("-", " ").split())
    aliases = {
        "papule": "papule",
        "papül": "papule",
        "pustule": "pustule",
        "püstül": "pustule",
        "nodule": "nodule",
        "nodül": "nodule",
        "comedone": "comedone",
        "komedon": "comedone",
        "blackhead": "comedone",
        "whitehead": "comedone",
    }
    return aliases.get(value, value)


def build_counts(detections: list[dict]) -> dict:
    counts = {key: 0 for key in COUNT_KEYS}
    unknown = 0

    for det in detections:
        label = _normalize_label(det.get("label_en") or det.get("label"))
        if label in counts:
            counts[label] += 1
        elif label == "inflammatory lesion":
            counts["papule"] += 1
        else:
            unknown += 1

    inflammatory_total = counts["papule"] + counts["pustule"] + counts["nodule"]
    weighted_score = sum(counts[key] * WEIGHTS[key] for key in COUNT_KEYS)

    return {
        **counts,
        "unknown": unknown,
        "inflammatory_total": inflammatory_total,
        "total": sum(counts.values()) + unknown,
        "weighted_score": round(weighted_score, 2),
    }


def hayashi_severity(inflammatory_total: int) -> dict:
    if inflammatory_total <= 0:
        return {
            "scale": "hayashi",
            "label": "clear",
            "label_tr": "Aktif inflamatuar lezyon yok",
            "score": 0,
        }
    if inflammatory_total <= 5:
        label, label_tr, score = "mild", "Hafif", 1
    elif inflammatory_total <= 20:
        label, label_tr, score = "moderate", "Orta", 2
    elif inflammatory_total <= 50:
        label, label_tr, score = "severe", "Şiddetli", 3
    else:
        label, label_tr, score = "very_severe", "Çok şiddetli", 4

    return {
        "scale": "hayashi",
        "label": label,
        "label_tr": label_tr,
        "score": score,
    }


def clinical_summary(counts: dict, severity: dict, quality: dict | None = None) -> str:
    parts = [
        f"{counts['inflammatory_total']} inflamatuar lezyon saptandı",
        f"Hayashi kriterine göre şiddet düzeyi: {severity['label_tr']}.",
    ]
    if counts.get("comedone", 0) > 0:
        parts.append(f"{counts['comedone']} komedon görsel raporda ayrıca işaretlendi.")
    if quality and not quality.get("quality_passed", True):
        parts.append("Görüntü kalitesi sınırlı olduğu için hekim doğrulaması önerilir.")
    return " ".join(parts)


def build_clinical_result(detections: list[dict], quality: dict | None = None) -> dict:
    counts = build_counts(detections)
    severity = hayashi_severity(int(counts["inflammatory_total"]))
    return {
        "counts": counts,
        "severity": severity,
        "clinical_summary": clinical_summary(counts, severity, quality),
        "weighted_score": counts["weighted_score"],
        "inflammatory_total": counts["inflammatory_total"],
    }


def compare_clinical_results(previous: dict, current: dict) -> dict:
    prev_counts = deepcopy(previous.get("counts") or {})
    curr_counts = deepcopy(current.get("counts") or {})

    deltas = {}
    for key in (*COUNT_KEYS, "inflammatory_total", "weighted_score"):
        deltas[key] = round(float(curr_counts.get(key, 0)) - float(prev_counts.get(key, 0)), 2)

    if deltas["nodule"] > 0 or deltas["pustule"] > 0 or deltas["weighted_score"] >= 3:
        trend, trend_tr = "worsening", "Kötüleşme"
    elif deltas["weighted_score"] <= -3 or deltas["inflammatory_total"] <= -5:
        trend, trend_tr = "improvement", "İyileşme"
    else:
        trend, trend_tr = "stable", "Stabil"

    return {
        "trend": trend,
        "trend_tr": trend_tr,
        "delta": deltas,
        "previous_severity": previous.get("severity"),
        "current_severity": current.get("severity"),
        "summary": _comparison_summary(trend_tr, deltas),
    }


def _comparison_summary(trend_tr: str, deltas: dict) -> str:
    direction = {
        "Kötüleşme": "artış",
        "İyileşme": "azalma",
        "Stabil": "belirgin değişim yok",
    }[trend_tr]
    return (
        f"Takip karşılaştırması: {trend_tr}. "
        f"İnflamatuar lezyon farkı {deltas['inflammatory_total']:+.0f}, "
        f"ağırlıklı skor farkı {deltas['weighted_score']:+.2f}; {direction}."
    )

