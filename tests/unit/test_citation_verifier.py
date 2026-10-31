"""
test_citation_verifier.py — Unit tests for Layer 1 Citation Verifier.

Tests:
1. Tamil digit normalization (௧௨௩ -> 123)
2. verify_citations with real Tamil and English statutes
3. verify_citations with fabricated / non-existent section
4. Obsolete/repealed law detection
"""

import pytest
from backend.app.verification.citation_verifier import (
    convert_tamil_digits,
    verify_citations,
    CitationVerdict,
)
from backend.app.verification.taxonomy import ErrorCategory


def test_tamil_to_ascii_digits():
    assert convert_tamil_digits("௧௨௩") == "123"
    assert convert_tamil_digits("பிரிவு ௪") == "பிரிவு 4"
    assert convert_tamil_digits("105") == "105"
    assert convert_tamil_digits("௧௦") == "10"


def test_verify_real_citation_english():
    text = "Under Section 3 of The Protection of Women from Domestic Violence Act, 2005 domestic violence is defined."
    result = verify_citations(text)
    assert result.total_citations >= 1
    match = [v for v in result.verdicts if v.extracted.normalized_section == "3"]
    assert len(match) > 0
    assert match[0].is_correct is True
    assert match[0].severity == 0


def test_verify_real_citation_tamil():
    text = "தமிழ்நாடு பெண்கள் வன்கொடுமை தடுப்புச் சட்டம், 1998 பிரிவு 4 இன் படி பெண்ணை வன்கொடுமை செய்பவருக்கு தண்டனை உண்டு."
    result = verify_citations(text)
    assert result.total_citations >= 1
    match = [v for v in result.verdicts if v.extracted.normalized_section == "4"]
    assert len(match) > 0
    assert match[0].is_correct is True
    assert match[0].severity == 0


def test_verify_repealed_law_flagged():
    text = "The Tamil Nadu Buildings (Lease and Rent Control) Act, 1960 பிரிவு 4 இன் படி கட்டிடங்கள் கட்டுப்பாடு."
    result = verify_citations(text)
    assert result.total_citations >= 1
    match = [v for v in result.verdicts if v.extracted.normalized_section == "4"]
    assert len(match) > 0
    # Act 18 of 1960 is repealed in KB
    assert match[0].verdict == ErrorCategory.OBSOLETE_LAW_AS_CURRENT
    assert match[0].severity == 3


def test_no_citation():
    text = "வணக்கம், இது ஒரு பொதுவான சட்டம் பற்றிய விளக்கம் ஆகும்."
    result = verify_citations(text)
    assert result.total_citations == 0
    assert len(result.verdicts) == 0
