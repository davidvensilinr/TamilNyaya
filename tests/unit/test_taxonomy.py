"""
test_taxonomy.py — Unit tests for Error Taxonomy and Severity.
"""

import pytest
from backend.app.verification.taxonomy import TAXONOMY, ErrorCategory, ErrorGroup, get_severity


def test_taxonomy_completeness():
    assert len(TAXONOMY) >= 10
    for cat, meta in TAXONOMY.items():
        assert meta.severity in (0, 1, 2, 3)
        assert meta.group in (ErrorGroup.FAITHFULNESS, ErrorGroup.FACTUALITY) or meta.severity == 0
        assert len(meta.description) > 0
        assert meta.layer in ("L1", "L2", "L3", "L1_or_L3")


def test_severity_classification():
    assert get_severity(ErrorCategory.CITATION_FABRICATION) == 3
    assert get_severity(ErrorCategory.JURISDICTION_CONFLATION) == 3
    assert get_severity(ErrorCategory.OBSOLETE_LAW_AS_CURRENT) == 3
    assert get_severity(ErrorCategory.UNSUPPORTED_ELABORATION) == 2
    assert get_severity(ErrorCategory.UNVERIFIABLE_CITATION) == 0
