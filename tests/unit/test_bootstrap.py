"""
test_bootstrap.py — Unit tests for percentile bootstrap confidence interval calculation.
"""

import pytest
from backend.app.pipeline.bootstrap import bootstrap_ci


def test_bootstrap_ci_basic():
    data = [1.0, 1.0, 1.0, 1.0, 0.0]  # mean 0.8
    ci_low, ci_high = bootstrap_ci(
        data,
        metric_fn=lambda sample: sum(sample) / len(sample),
        alpha=0.05,
    )
    assert ci_low is not None
    assert ci_high is not None
    assert 0.0 <= ci_low <= ci_high <= 1.0
    assert ci_low < 0.8 < ci_high


def test_bootstrap_ci_empty():
    ci_low, ci_high = bootstrap_ci([], metric_fn=lambda s: 0.0)
    assert ci_low is None
    assert ci_high is None
