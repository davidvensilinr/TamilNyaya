"""
test_integrity.py — Unit test verifying that the 7 integrity checks run and pass.
"""

import pytest
from backend.app.integrity import run_integrity_checks


def test_integrity_checks():
    report = run_integrity_checks()
    assert "overall" in report
    assert report["overall"] == "pass"
    assert "checks" in report
    assert len(report["checks"]) == 7
    assert report["passed"] >= 6
