"""
agreement.py — Inter-annotator agreement (Cohen's kappa).

Computes kappa ONLY from real human annotations in the Annotation table.
Never from fabricated or generated labels.

Formula:
  κ = (pₒ − pₑ) / (1 − pₑ)
where pₒ = observed agreement, pₑ = expected agreement by chance.
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Optional

from ..db import Annotation


def compute_kappa_per_category(
    annotations: list[Annotation],
) -> dict[str, dict]:
    """
    Compute Cohen's kappa for each error category.

    Requires at least two distinct annotators for each item.
    Only items with exactly two annotators contribute to kappa
    (adjudicated items are excluded from agreement computation).

    Returns
    -------
    {
        "CitationFabrication": {"kappa": 0.72, "n": 45, "po": 0.85, "pe": 0.48},
        ...
    }
    """
    # Group annotations by item_id
    by_item: dict[str, list[Annotation]] = defaultdict(list)
    for ann in annotations:
        if not ann.is_adjudicated:
            by_item[ann.item_id].append(ann)

    # Filter to items with exactly 2 annotators (double annotation)
    paired: list[tuple[Annotation, Annotation]] = []
    for item_id, anns in by_item.items():
        annotators = list({a.annotator_id for a in anns})
        if len(annotators) == 2:
            a1 = next(a for a in anns if a.annotator_id == annotators[0])
            a2 = next(a for a in anns if a.annotator_id == annotators[1])
            paired.append((a1, a2))

    if not paired:
        return {}

    # Collect all categories across the corpus
    all_categories: set[str] = set()
    for a1, a2 in paired:
        cats1 = set(json.loads(a1.error_categories))
        cats2 = set(json.loads(a2.error_categories))
        all_categories.update(cats1)
        all_categories.update(cats2)

    # Per-category binary kappa
    result: dict[str, dict] = {}
    for cat in sorted(all_categories):
        n = len(paired)
        # Contingency table for binary (present / absent)
        a_count = 0  # both say present
        b_count = 0  # ann1 present, ann2 absent
        c_count = 0  # ann1 absent, ann2 present
        d_count = 0  # both say absent

        for a1, a2 in paired:
            cats1 = set(json.loads(a1.error_categories))
            cats2 = set(json.loads(a2.error_categories))
            in1 = cat in cats1
            in2 = cat in cats2
            if in1 and in2:
                a_count += 1
            elif in1 and not in2:
                b_count += 1
            elif not in1 and in2:
                c_count += 1
            else:
                d_count += 1

        po = (a_count + d_count) / n if n > 0 else 0.0
        p1 = (a_count + b_count) / n if n > 0 else 0.0
        p2 = (a_count + c_count) / n if n > 0 else 0.0
        q1 = 1.0 - p1
        q2 = 1.0 - p2
        pe = (p1 * p2) + (q1 * q2)

        kappa: Optional[float] = None
        if abs(1.0 - pe) > 1e-9:
            kappa = round((po - pe) / (1.0 - pe), 4)

        result[cat] = {
            "kappa": kappa,
            "n": n,
            "po": round(po, 4),
            "pe": round(pe, 4),
            "both_present": a_count,
            "both_absent": d_count,
            "disagree": b_count + c_count,
        }

    return result


def compute_severity_agreement(annotations: list[Annotation]) -> dict:
    """
    Compute agreement on severity ratings (1, 2, 3) between paired annotators.
    Returns exact match rate and weighted kappa.
    """
    by_item: dict[str, list[Annotation]] = defaultdict(list)
    for ann in annotations:
        if not ann.is_adjudicated:
            by_item[ann.item_id].append(ann)

    paired = []
    for item_id, anns in by_item.items():
        annotators = list({a.annotator_id for a in anns})
        if len(annotators) == 2:
            a1 = next(a for a in anns if a.annotator_id == annotators[0])
            a2 = next(a for a in anns if a.annotator_id == annotators[1])
            paired.append((a1.severity, a2.severity))

    if not paired:
        return {
            "n": 0,
            "exact_match_rate": None,
            "note": "No paired annotations available for severity agreement.",
        }

    exact = sum(1 for s1, s2 in paired if s1 == s2)
    n = len(paired)

    return {
        "n": n,
        "exact_match_rate": round(exact / n, 4) if n > 0 else None,
        "exact_matches": exact,
        "note": f"Based on {n} items with double annotation.",
    }
