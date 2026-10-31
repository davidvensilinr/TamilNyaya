"""
loader.py — Bulk-loads parsed Acts and Sections into the KB database.

Every record receives mandatory provenance fields.  Records that fail
validation are logged and rejected — never silently inserted with empty
provenance.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from ..db import KBRecord, ActCoverage, get_db_session
from .. import audit as audit_mod
from ingest.parsers.html_parser import ParsedAct, ParsedSection, PARSER_NAME_AND_VERSION, EXTRACTION_METHOD


@dataclass
class LoadResult:
    act_name_en: str
    sections_attempted: int
    sections_inserted: int
    sections_rejected: int
    rejection_reasons: list[str]
    warnings: list[str]


def load_parsed_act(parsed: ParsedAct) -> LoadResult:
    """
    Insert a ParsedAct and its sections into the knowledge base.

    Rules:
    - Records with missing mandatory provenance are rejected with a logged reason.
    - Duplicates (same sha256 + section_no) are skipped, not duplicated.
    - Every rejection is recorded in the audit log.
    """
    rejected = 0
    inserted = 0
    rejection_reasons: list[str] = []
    now = datetime.now(timezone.utc)

    # Validate mandatory act-level fields
    act_name_en = parsed.act_name_en.strip()
    act_name_ta = parsed.act_name_ta.strip()

    if not act_name_en and not act_name_ta:
        reason = f"Both act_name_en and act_name_ta are empty for {parsed.source_url}"
        audit_mod.log_error("kb_load_reject", reason, source_url=parsed.source_url)
        return LoadResult(
            act_name_en="UNKNOWN",
            sections_attempted=len(parsed.sections),
            sections_inserted=0,
            sections_rejected=len(parsed.sections),
            rejection_reasons=[reason],
            warnings=parsed.parse_warnings,
        )

    # Use the non-empty name as English if only one is present
    if not act_name_en:
        act_name_en = act_name_ta  # best available

    with get_db_session() as session:
        for sec in parsed.sections:
            reason = _validate_section(sec, parsed)
            if reason:
                rejected += 1
                rejection_reasons.append(reason)
                audit_mod.log(
                    action="kb_section_reject",
                    detail=f"Rejected section {sec.section_no}: {reason}",
                    level=audit_mod.AuditLevel.WARNING,
                    source_url=parsed.source_url,
                )
                continue

            # Check for duplicate
            exists = (
                session.query(KBRecord)
                .filter_by(
                    source_file_sha256=parsed.source_file_sha256,
                    section_no=sec.section_no,
                )
                .first()
            )
            if exists:
                audit_mod.log(
                    action="kb_section_duplicate",
                    detail=f"Skipped duplicate: sha256={parsed.source_file_sha256[:12]}… section={sec.section_no}",
                    source_url=parsed.source_url,
                )
                continue

            record = KBRecord(
                record_id=str(uuid.uuid4()),
                act_name_ta=act_name_ta or act_name_en,
                act_name_en=act_name_en,
                section_no=sec.section_no,
                text_ta=sec.text_ta or "",
                text_en=sec.text_en,
                jurisdiction=parsed.jurisdiction,
                in_force=parsed.in_force,
                repealed_by=parsed.repealed_by,
                as_of_date=parsed.as_of_date,
                source_url=parsed.source_url,
                source_document_title=parsed.source_document_title,
                source_file_sha256=parsed.source_file_sha256,
                retrieved_at=parsed.retrieved_at or now,
                parser_name_and_version=PARSER_NAME_AND_VERSION,
                extraction_method=EXTRACTION_METHOD,
                ocr_confidence=None,
                raw_span=sec.raw_span,
            )
            session.add(record)
            inserted += 1

        # Update coverage table
        _update_coverage(session, act_name_en, parsed.jurisdiction, inserted)
        session.commit()

    audit_mod.log(
        action="kb_act_loaded",
        detail=(
            f"Loaded '{act_name_en}': {inserted} inserted, "
            f"{rejected} rejected out of {len(parsed.sections)} sections"
        ),
        source_url=parsed.source_url,
    )

    return LoadResult(
        act_name_en=act_name_en,
        sections_attempted=len(parsed.sections),
        sections_inserted=inserted,
        sections_rejected=rejected,
        rejection_reasons=rejection_reasons,
        warnings=parsed.parse_warnings,
    )


def _validate_section(sec: ParsedSection, parsed: ParsedAct) -> Optional[str]:
    """Return a rejection reason string, or None if the section is valid."""
    if not sec.section_no or not sec.section_no.strip():
        return "section_no is empty"
    if not sec.text_ta and not sec.text_en:
        return "both text_ta and text_en are empty"
    if not parsed.source_file_sha256:
        return "source_file_sha256 is missing"
    if not parsed.source_url:
        return "source_url is missing"
    return None


def _update_coverage(
    session,
    act_name_en: str,
    jurisdiction: str,
    new_sections: int,
) -> None:
    now = datetime.now(timezone.utc)
    cov = session.query(ActCoverage).filter_by(act_name_en=act_name_en).first()
    if cov:
        cov.sections_ingested += new_sections
        cov.last_updated = now
    else:
        session.add(
            ActCoverage(
                act_name_en=act_name_en,
                jurisdiction=jurisdiction,
                sections_in_source=None,   # unknown until we can count from source
                sections_ingested=new_sections,
                last_updated=now,
            )
        )
