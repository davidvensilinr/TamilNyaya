"""
test_aggregator.py — Unit tests for evaluation metric aggregators.
"""

import json
from datetime import datetime, timezone
import pytest
from backend.app.db import RunResult
from backend.app.pipeline.aggregator import (
    compute_citation_accuracy,
    compute_hallucination_rates,
    compute_jurisdiction_confusion,
    compute_adversarial_delta,
)


def _make_mock_result(layer1_correct=1, layer1_total=1, max_severity=0, error_cats=None):
    now = datetime.now(timezone.utc)
    l1_json = json.dumps({
        "total_citations": layer1_total,
        "correct_citations": layer1_correct,
        "verdicts": [
            {
                "raw_text": "Section 1",
                "is_correct": layer1_correct > 0,
                "severity": max_severity,
                "verdict": error_cats[0] if error_cats else "CORRECT",
                "branch_fired": "CORRECT" if layer1_correct > 0 else "TEST",
            }
        ] if layer1_total > 0 else [],
    })
    return RunResult(
        run_id="run-test",
        item_id="item-test",
        timestamp=now,
        user_prompt="test",
        raw_response="test response",
        layer1_result=l1_json,
        error_categories=json.dumps(error_cats or []),
        max_severity=max_severity if max_severity > 0 else None,
    )


def test_compute_citation_accuracy():
    r1 = _make_mock_result(layer1_correct=1, layer1_total=1)
    r2 = _make_mock_result(layer1_correct=0, layer1_total=1)
    acc = compute_citation_accuracy([r1, r2])
    assert acc == 0.5


def test_compute_hallucination_rates():
    r1 = _make_mock_result(max_severity=3, error_cats=["CitationFabrication"])
    r2 = _make_mock_result(max_severity=0, error_cats=[])
    rates = compute_hallucination_rates([r1, r2])
    assert rates["severity3_rate"] == 0.5
    assert rates["severity2_rate"] == 0.0
