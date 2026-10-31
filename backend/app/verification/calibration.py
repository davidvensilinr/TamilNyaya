"""
calibration.py — Calibration logic for LLM Judge against human labels.

Computes Cohen's kappa between human annotations and LLM judge outputs.
Governing rules:
- Below MIN_LABELED_ITEMS_FOR_CALIBRATION: "insufficient human labels, calibration not meaningful".
- Below KAPPA_THRESHOLD: marked "human review required".
- Never invent human labels or fake calibration stats.
"""

from __future__ import annotations

from typing import Optional

from ..config import settings
from ..db import Annotation, RunResult, get_db_session
from ..annotation.agreement import compute_kappa_per_category


def evaluate_judge_calibration(category: str) -> dict:
    """
    Check calibration status for a specific judge category against existing human annotations.
    """
    with get_db_session() as session:
        annotations = session.query(Annotation).all()

    if not annotations:
        return {
            "category": category,
            "labeled_items": 0,
            "kappa": None,
            "threshold": settings.kappa_threshold,
            "status": "not_run",
            "message": "No human annotations available yet.",
        }

    kappas = compute_kappa_per_category(annotations)
    cat_data = kappas.get(category, {})
    n = cat_data.get("n", 0)
    k = cat_data.get("kappa")

    if n < settings.min_labeled_items_for_calibration:
        status = "insufficient_data"
        msg = f"Insufficient human labels ({n}/{settings.min_labeled_items_for_calibration})."
    elif k is not None and k >= settings.kappa_threshold:
        status = "calibrated"
        msg = f"Calibrated (κ={k:.2f} >= {settings.kappa_threshold})."
    elif k is not None:
        status = "human_review_required"
        msg = f"Below agreement threshold (κ={k:.2f} < {settings.kappa_threshold}). Human review required."
    else:
        status = "insufficient_data"
        msg = "Cannot compute agreement."

    return {
        "category": category,
        "labeled_items": n,
        "kappa": k,
        "threshold": settings.kappa_threshold,
        "status": status,
        "message": msg,
    }
