"""
aggregator.py — Metrics computed from stored raw results.

All metric functions handle empty input by returning None plus a reason.
No function raises on empty or missing data.
Every function's formula is documented here and mirrored in the API's
/metrics/{name}/explain endpoint.
"""

from __future__ import annotations

import json
from typing import Optional

from ..db import RunResult, BenchmarkItem, get_db_session
from ..verification.taxonomy import ErrorCategory


def compute_citation_accuracy(results: list[RunResult]) -> Optional[float]:
    """
    Citation Accuracy = correct_citations / total_verifiable_citations.

    Excludes UnverifiableCitation from denominator.
    Returns None when no verifiable citations exist.
    """
    total_verifiable = 0
    correct = 0

    for r in results:
        if not r.layer1_result:
            continue
        l1 = json.loads(r.layer1_result)
        for v in l1.get("verdicts", []):
            verdict = v.get("verdict", "")
            # UnverifiableCitation is excluded from denominator
            if verdict == ErrorCategory.UNVERIFIABLE_CITATION.value:
                continue
            total_verifiable += 1
            if v.get("is_correct") or v.get("branch_fired", "").startswith("CORRECT"):
                correct += 1

    if total_verifiable == 0:
        return None
    return round(correct / total_verifiable, 4)


def compute_hallucination_rates(results: list[RunResult]) -> dict[str, Optional[float]]:
    """
    Returns hallucination rates by severity tier.
    severity3_rate = count(max_severity=3) / total_items
    """
    if not results:
        return {"severity1_rate": None, "severity2_rate": None, "severity3_rate": None}

    total = len(results)
    counts = {1: 0, 2: 0, 3: 0}
    for r in results:
        if r.max_severity and r.max_severity in counts:
            counts[r.max_severity] += 1

    return {
        "severity1_rate": round(counts[1] / total, 4),
        "severity2_rate": round(counts[2] / total, 4),
        "severity3_rate": round(counts[3] / total, 4),
        "total_items": total,
        "counts": counts,
    }


def compute_jurisdiction_confusion(results: list[RunResult]) -> Optional[float]:
    """
    Jurisdiction Confusion Rate = JurisdictionConflation errors / jurisdiction_probe items.
    """
    probe_results = []
    for r in results:
        with get_db_session() as session:
            item = session.query(BenchmarkItem).filter_by(item_id=r.item_id).first()
            if item and item.task_family == "jurisdiction_probe":
                probe_results.append(r)

    if not probe_results:
        return None

    confused = 0
    for r in probe_results:
        if not r.layer1_result:
            continue
        l1 = json.loads(r.layer1_result)
        for v in l1.get("verdicts", []):
            if v.get("verdict") == ErrorCategory.JURISDICTION_CONFLATION.value:
                confused += 1
                break

    return round(confused / len(probe_results), 4)


def compute_adversarial_delta(results: list[RunResult]) -> Optional[float]:
    """
    Adversarial Robustness Δ = accuracy_clean - accuracy_adversarial.
    """
    clean_results, adv_results = [], []

    for r in results:
        with get_db_session() as session:
            item = session.query(BenchmarkItem).filter_by(item_id=r.item_id).first()
        if not item:
            continue
        if item.is_adversarial:
            adv_results.append(r)
        else:
            clean_results.append(r)

    acc_clean = compute_citation_accuracy(clean_results)
    acc_adv = compute_citation_accuracy(adv_results)

    if acc_clean is None or acc_adv is None:
        return None
    return round(acc_clean - acc_adv, 4)


def compute_fairness_gaps(results: list[RunResult]) -> dict:
    """
    Fairness gaps:
    - jurisdiction_gap = |rate(Central) - rate(Tamil Nadu)|
    - topic_gap = rate(underrepresented) - rate(commonly discussed)
    """
    by_jur: dict[str, list[RunResult]] = {}
    by_topic: dict[str, list[RunResult]] = {}

    for r in results:
        with get_db_session() as session:
            item = session.query(BenchmarkItem).filter_by(item_id=r.item_id).first()
        if not item:
            continue
        by_jur.setdefault(item.jurisdiction, []).append(r)
        by_topic.setdefault(item.topic_tag, []).append(r)

    jur_gap = None
    central_rate = compute_citation_accuracy(by_jur.get("Central", []))
    tn_rate = compute_citation_accuracy(by_jur.get("Tamil Nadu", []))
    if central_rate is not None and tn_rate is not None:
        jur_gap = round(abs(central_rate - tn_rate), 4)

    topic_breakdown = {
        topic: compute_citation_accuracy(topic_results)
        for topic, topic_results in by_topic.items()
    }

    return {
        "jurisdiction_gap": jur_gap,
        "central_citation_accuracy": central_rate,
        "tn_citation_accuracy": tn_rate,
        "topic_breakdown": topic_breakdown,
        "note": (
            "Jurisdiction gap = |accuracy(Central) − accuracy(Tamil Nadu)|. "
            "Topic gaps are shown as per-topic accuracy."
        ),
    }
