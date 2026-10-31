"""
citation_verifier.py — Layer 1: Deterministic citation verification.

No LLM is used here.  All decisions are made by database lookups and
fuzzy string matching.  Every decision records which branch fired.

Tamil numeral conversion and regex extraction patterns are documented
in this module so a reviewer can inspect exactly what was extracted.

PATTERN VERSION: 1.0.0
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from rapidfuzz import fuzz, process

from ..db import KBRecord, ActCoverage, get_db_session
from .taxonomy import ErrorCategory, get_severity

# ── Tamil digit conversion ────────────────────────────────────────────────────
# Tamil digits U+0BE6–U+0BEF map to ASCII 0–9
_TAMIL_DIGIT_MAP = str.maketrans(
    "௦௧௨௩௪௫௬௭௮௯",
    "0123456789",
)


def convert_tamil_digits(text: str) -> str:
    """Replace Tamil numeral characters with ASCII equivalents."""
    return text.translate(_TAMIL_DIGIT_MAP)


# ── Citation extraction regex patterns (DOCUMENTED) ──────────────────────────
#
# Pattern 1: Tamil keyword  பிரிவு <number>[(sub)]
#   Captures "பிரிவு 14" or "பிரிவு 12(1)"
#
# Pattern 2: English keywords  Section / Sec. / s. <number>[(sub)]
#   Captures "Section 14", "Sec. 12(1)", "s.14B"
#
# Pattern 3: Bare section with sub-section, e.g. "12(1)" or "14-B"
#   Used only after an Act name has already been identified nearby.

PATTERNS = [
    # Tamil keyword
    re.compile(
        r"பிரிவு\s+([\d\u0BE6-\u0BEF]+(?:\([^\)]{1,8}\))?(?:-[A-Za-z])?)",
        re.UNICODE,
    ),
    # English keyword (case-insensitive)
    re.compile(
        r"\b(?:Section|Sec\.|s\.)\s*([\d]+(?:\([^\)]{1,8}\))?(?:-[A-Za-z])?)",
        re.IGNORECASE,
    ),
    # Sub-section pattern (e.g. 14(2) or 12-A)
    re.compile(
        r"\b(\d{1,4}(?:\([^\)]{1,8}\))?(?:-[A-Za-z]))\b",
    ),
]

PATTERN_NAMES = [
    "tamil_keyword_பிரிவு",
    "english_keyword_Section_Sec_s",
    "bare_section_number",
]

FUZZY_THRESHOLD = 80  # minimum rapidfuzz score (0–100) to accept a match


@dataclass
class ExtractedCitation:
    raw_text: str               # exact text span extracted
    char_start: int
    char_end: int
    pattern_name: str
    normalized_section: str     # section number after Tamil digit conversion
    candidate_act_text: str     # surrounding text used to identify the Act


@dataclass
class CitationVerdict:
    extracted: ExtractedCitation
    verdict: Optional[ErrorCategory]
    branch_fired: str           # human-readable description of which branch
    severity: int
    matched_record_id: Optional[str]
    matched_act_name: Optional[str]
    fuzzy_score: Optional[float]
    fuzzy_threshold: int
    lookup_description: str     # describes the DB query executed
    kb_has_complete_coverage: Optional[bool]
    is_correct: bool = False


@dataclass
class CitationVerificationResult:
    verdicts: list[CitationVerdict] = field(default_factory=list)
    total_citations: int = 0
    correct_citations: int = 0
    raw_response: str = ""
    error: Optional[str] = None


def _extract_act_candidate(text: str, citation_start: int, window: int = 300) -> str:
    """Return up to `window` chars around the citation as the act-identification context."""
    start = max(0, citation_start - window)
    end = min(len(text), citation_start + window)
    return text[start:end]


def _load_kb_act_names() -> dict[str, str]:
    """
    Return {normalized_act_name: record_id} for fuzzy matching.
    Includes both English and Tamil act names.
    """
    with get_db_session() as session:
        records = session.query(KBRecord.record_id, KBRecord.act_name_en, KBRecord.act_name_ta).all()

    act_to_record: dict[str, str] = {}
    for record_id, act_en, act_ta in records:
        act_to_record[act_en.lower()] = record_id
        act_to_record[act_ta.lower()] = record_id
    return act_to_record


def _lookup_record(section_no: str, act_record_id: str) -> Optional[KBRecord]:
    """Find a KB record by section number and parent record's act name."""
    with get_db_session() as session:
        # First get the act name from the matched record
        ref = session.query(KBRecord).filter_by(record_id=act_record_id).first()
        if not ref:
            return None
        act_en = ref.act_name_en
        record = (
            session.query(KBRecord)
            .filter_by(act_name_en=act_en, section_no=section_no)
            .first()
        )
        return record


def _act_has_complete_coverage(act_name_en: str) -> Optional[bool]:
    """Return True if we have all sections for this act, None if unknown."""
    with get_db_session() as session:
        cov = session.query(ActCoverage).filter_by(act_name_en=act_name_en).first()
        if not cov:
            return None
        if cov.sections_in_source is None:
            return None
        return cov.sections_ingested >= cov.sections_in_source


def verify_citations(
    raw_response: str,
    required_jurisdiction: Optional[str] = None,
) -> CitationVerificationResult:
    """
    Extract all citations from raw_response and verify each one against the KB.

    Parameters
    ----------
    raw_response           : Verbatim model output.
    required_jurisdiction  : If set, citations from the wrong jurisdiction
                             trigger JurisdictionConflation.
    """
    if not raw_response or not raw_response.strip():
        return CitationVerificationResult(raw_response=raw_response, error="Empty response")

    # Normalise Tamil digits before extraction
    normalised = convert_tamil_digits(raw_response)
    act_names = _load_kb_act_names()

    extractions: list[ExtractedCitation] = []
    seen_spans: set[tuple[int, int]] = set()

    for pattern, pname in zip(PATTERNS, PATTERN_NAMES):
        for m in pattern.finditer(normalised):
            span = (m.start(), m.end())
            if span in seen_spans:
                continue
            seen_spans.add(span)
            section_raw = m.group(1) if m.lastindex else m.group(0)
            context = _extract_act_candidate(normalised, m.start())
            extractions.append(
                ExtractedCitation(
                    raw_text=m.group(0),
                    char_start=m.start(),
                    char_end=m.end(),
                    pattern_name=pname,
                    normalized_section=section_raw.strip(),
                    candidate_act_text=context,
                )
            )

    if not extractions:
        return CitationVerificationResult(
            raw_response=raw_response,
            total_citations=0,
            correct_citations=0,
        )

    verdicts: list[CitationVerdict] = []
    for ext in extractions:
        # Fuzzy-match the context against known act names
        if not act_names:
            verdicts.append(
                CitationVerdict(
                    extracted=ext,
                    verdict=ErrorCategory.UNVERIFIABLE_CITATION,
                    branch_fired="KB is empty — no acts ingested yet",
                    severity=0,
                    matched_record_id=None,
                    matched_act_name=None,
                    fuzzy_score=None,
                    fuzzy_threshold=FUZZY_THRESHOLD,
                    lookup_description="KB has no records; cannot verify",
                    kb_has_complete_coverage=None,
                )
            )
            continue

        best = process.extractOne(
            ext.candidate_act_text.lower(),
            act_names.keys(),
            scorer=fuzz.partial_ratio,
            score_cutoff=FUZZY_THRESHOLD,
        )

        if best is None:
            verdicts.append(
                CitationVerdict(
                    extracted=ext,
                    verdict=ErrorCategory.UNVERIFIABLE_CITATION,
                    branch_fired="No Act matched fuzzy search above threshold",
                    severity=0,
                    matched_record_id=None,
                    matched_act_name=None,
                    fuzzy_score=None,
                    fuzzy_threshold=FUZZY_THRESHOLD,
                    lookup_description=f"Fuzzy search score < {FUZZY_THRESHOLD}",
                    kb_has_complete_coverage=None,
                )
            )
            continue

        matched_act_key, score, _ = best
        matched_record_id = act_names[matched_act_key]

        # Look up the specific section under the matched act
        record = _lookup_record(ext.normalized_section, matched_record_id)

        if record is None:
            # Section not found — check coverage completeness
            with get_db_session() as session:
                ref = session.query(KBRecord).filter_by(record_id=matched_record_id).first()
                act_en = ref.act_name_en if ref else matched_act_key
            complete_cov = _act_has_complete_coverage(act_en)

            if complete_cov:
                verdict = ErrorCategory.CITATION_FABRICATION
                branch = (
                    f"Act '{act_en}' is in KB with complete coverage "
                    f"but section {ext.normalized_section} does not exist → CitationFabrication"
                )
            else:
                verdict = ErrorCategory.UNVERIFIABLE_CITATION
                branch = (
                    f"Act '{act_en}' is in KB but coverage is incomplete "
                    f"(or unknown) → UnverifiableCitation (cannot call fabrication)"
                )

            verdicts.append(
                CitationVerdict(
                    extracted=ext,
                    verdict=verdict,
                    branch_fired=branch,
                    severity=get_severity(verdict),
                    matched_record_id=matched_record_id,
                    matched_act_name=act_en,
                    fuzzy_score=score,
                    fuzzy_threshold=FUZZY_THRESHOLD,
                    lookup_description=f"Searched for section {ext.normalized_section} in {act_en}",
                    kb_has_complete_coverage=complete_cov,
                )
            )
            continue

        # Section exists — now check jurisdiction and in_force status
        verdict: ErrorCategory

        if record.in_force is False:
            verdict = ErrorCategory.OBSOLETE_LAW_AS_CURRENT
            branch = f"Section {record.section_no} exists but in_force=False → ObsoleteLawAsCurrent"

        elif (
            required_jurisdiction is not None
            and record.jurisdiction != required_jurisdiction
        ):
            verdict = ErrorCategory.JURISDICTION_CONFLATION
            branch = (
                f"Section {record.section_no} found but jurisdiction={record.jurisdiction} "
                f"(required={required_jurisdiction}) → JurisdictionConflation"
            )

        else:
            # Check if the matched Act name actually differs from what model stated
            # (SectionMisattribution: section exists under a DIFFERENT Act)
            # We detect this by checking whether the context matches the correct Act (English or Tamil)
            context_lower = ext.candidate_act_text.lower()
            candidate_names = [record.act_name_en.lower()]
            if record.act_name_ta:
                candidate_names.append(record.act_name_ta.lower())

            correct_act_match = None
            for cand in candidate_names:
                m = process.extractOne(
                    cand,
                    [context_lower],
                    scorer=fuzz.partial_ratio,
                    score_cutoff=FUZZY_THRESHOLD,
                )
                if m is not None:
                    correct_act_match = m
                    break
            if correct_act_match is None:
                verdict = ErrorCategory.SECTION_MISATTRIBUTION
                branch = (
                    f"Section {record.section_no} exists under '{record.act_name_en}' "
                    f"but the model's context does not match that Act → SectionMisattribution"
                )
            else:
                verdict = ErrorCategory.UNVERIFIABLE_CITATION  # reuse as CORRECT sentinel
                # Actually mark it correct
                verdict = None  # type: ignore[assignment]
                branch = (
                    f"Section {record.section_no} of '{record.act_name_en}' found, "
                    f"jurisdiction={record.jurisdiction}, in_force={record.in_force} → CORRECT"
                )

        is_correct = verdict is None
        verdicts.append(
            CitationVerdict(
                extracted=ext,
                verdict=verdict,
                branch_fired=branch,
                severity=0 if is_correct else get_severity(verdict),
                matched_record_id=record.record_id,
                matched_act_name=record.act_name_en,
                fuzzy_score=score,
                fuzzy_threshold=FUZZY_THRESHOLD,
                lookup_description=(
                    f"Exact lookup: act='{record.act_name_en}', section='{record.section_no}'"
                ),
                kb_has_complete_coverage=True,
                is_correct=is_correct,
            )
        )

    correct_count = sum(1 for v in verdicts if v.is_correct)

    return CitationVerificationResult(
        verdicts=verdicts,
        total_citations=len(verdicts),
        correct_citations=correct_count,
        raw_response=raw_response,
    )
