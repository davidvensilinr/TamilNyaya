"""
quality_report.py — Data-quality report generator for TamilNyaya-Bench.

Generates a comprehensive quality report from the KB records, including:
- Records ingested and rejected
- OCR confidence distribution (if applicable)
- Duplicates check
- Section-number consistency
- Random sample for human spot-checking

All data comes from the actual database — no synthetic values.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import sys
from pathlib import Path

# Ensure workspace root is on sys.path
WORKSPACE = Path(__file__).resolve().parent.parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from backend.app.db import KBRecord, ActCoverage, AuditEntry, get_db_session, create_all_tables


@dataclass
class QualityReportData:
    generated_at: str
    total_records: int = 0
    total_acts: int = 0
    by_jurisdiction: dict[str, int] = field(default_factory=dict)
    by_extraction_method: dict[str, int] = field(default_factory=dict)
    records_with_empty_tamil: int = 0
    records_with_empty_english: int = 0
    ocr_records: int = 0
    ocr_confidence_stats: Optional[dict] = None
    coverage_summary: list[dict] = field(default_factory=list)
    section_consistency: list[dict] = field(default_factory=list)
    rejection_log: list[dict] = field(default_factory=list)
    spot_check_sample: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def generate_quality_report(sample_size: int = 5, seed: int = 42) -> QualityReportData:
    """Generate a comprehensive data-quality report from the actual KB."""
    create_all_tables()
    rng = random.Random(seed)
    report = QualityReportData(generated_at=datetime.now(timezone.utc).isoformat())

    with get_db_session() as session:
        all_records = session.query(KBRecord).all()
        report.total_records = len(all_records)

        if report.total_records == 0:
            report.warnings.append("No records in KB. Run ingestion first.")
            return report

        # By jurisdiction
        for r in all_records:
            report.by_jurisdiction[r.jurisdiction] = report.by_jurisdiction.get(r.jurisdiction, 0) + 1

        # By extraction method
        for r in all_records:
            report.by_extraction_method[r.extraction_method] = (
                report.by_extraction_method.get(r.extraction_method, 0) + 1
            )

        # Empty text counts
        report.records_with_empty_tamil = sum(1 for r in all_records if not r.text_ta or not r.text_ta.strip())
        report.records_with_empty_english = sum(1 for r in all_records if not r.text_en or not r.text_en.strip())

        # OCR stats
        ocr_records = [r for r in all_records if r.extraction_method == "ocr"]
        report.ocr_records = len(ocr_records)
        if ocr_records:
            confidences = [r.ocr_confidence for r in ocr_records if r.ocr_confidence is not None]
            if confidences:
                report.ocr_confidence_stats = {
                    "count": len(confidences),
                    "mean": round(sum(confidences) / len(confidences), 3),
                    "min": round(min(confidences), 3),
                    "max": round(max(confidences), 3),
                }

        # Unique acts
        acts = set(r.act_name_en for r in all_records)
        report.total_acts = len(acts)

        # Coverage summary
        coverages = session.query(ActCoverage).all()
        for cov in coverages:
            pct = None
            if cov.sections_in_source and cov.sections_in_source > 0:
                pct = round(cov.sections_ingested / cov.sections_in_source * 100, 1)
            report.coverage_summary.append({
                "act_name_en": cov.act_name_en,
                "jurisdiction": cov.jurisdiction,
                "sections_in_source": cov.sections_in_source,
                "sections_ingested": cov.sections_ingested,
                "coverage_pct": pct,
            })

        # Section-number consistency
        for act in acts:
            act_records = [r for r in all_records if r.act_name_en == act]
            section_nos = [r.section_no for r in act_records]
            duplicates = [s for s in section_nos if section_nos.count(s) > 1]
            if duplicates:
                report.section_consistency.append({
                    "act": act,
                    "issue": "duplicate_section_numbers",
                    "sections": list(set(duplicates)),
                })
            # Check for non-standard section numbering
            for s in section_nos:
                import re
                if not re.match(r"^\d+[A-Za-z]?(-[A-Za-z0-9]+)?$", s):
                    report.section_consistency.append({
                        "act": act,
                        "issue": "non_standard_section_number",
                        "section": s,
                    })

        # Rejection log from audit
        rejections = (
            session.query(AuditEntry)
            .filter(AuditEntry.action.in_(["kb_section_reject", "kb_load_reject"]))
            .all()
        )
        for rej in rejections:
            report.rejection_log.append({
                "timestamp": rej.timestamp.isoformat(),
                "action": rej.action,
                "detail": rej.detail,
                "source_url": rej.source_url,
            })

        # Random spot-check sample
        sample_records = rng.sample(all_records, min(sample_size, len(all_records)))
        for r in sample_records:
            report.spot_check_sample.append({
                "record_id": r.record_id,
                "act_name_en": r.act_name_en,
                "section_no": r.section_no,
                "jurisdiction": r.jurisdiction,
                "text_ta_preview": r.text_ta[:200] if r.text_ta else "(empty)",
                "text_en_preview": (r.text_en[:200] if r.text_en else "(not available)"),
                "source_url": r.source_url,
                "source_file_sha256": r.source_file_sha256[:16] + "...",
                "extraction_method": r.extraction_method,
                "raw_span": r.raw_span,
            })

    return report


def print_report(report: QualityReportData) -> None:
    """Print a human-readable quality report."""
    print("=" * 70)
    print("TamilNyaya-Bench — Data Quality Report")
    print(f"Generated: {report.generated_at}")
    print("=" * 70)

    print(f"\nTotal KB records: {report.total_records}")
    print(f"Total Acts: {report.total_acts}")
    print(f"By jurisdiction: {report.by_jurisdiction}")
    print(f"By extraction method: {report.by_extraction_method}")
    print(f"Records with empty Tamil text: {report.records_with_empty_tamil}")
    print(f"Records with empty English text: {report.records_with_empty_english}")
    print(f"OCR records: {report.ocr_records}")

    if report.ocr_confidence_stats:
        print(f"OCR confidence: {report.ocr_confidence_stats}")

    print("\n--- Coverage Summary ---")
    for cov in report.coverage_summary:
        pct_str = f"{cov['coverage_pct']}%" if cov['coverage_pct'] else "unknown"
        print(f"  {cov['act_name_en']}: {cov['sections_ingested']}/{cov['sections_in_source'] or '?'} ({pct_str})")

    if report.section_consistency:
        print("\n--- Section Consistency Issues ---")
        for issue in report.section_consistency:
            print(f"  {issue['act']}: {issue['issue']} - {issue.get('sections', issue.get('section'))}")
    else:
        print("\n--- Section Consistency: OK (no issues found) ---")

    if report.rejection_log:
        print(f"\n--- Rejections ({len(report.rejection_log)}) ---")
        for rej in report.rejection_log:
            print(f"  [{rej['timestamp']}] {rej['detail']}")
    else:
        print("\n--- Rejections: None ---")

    print(f"\n--- Spot-Check Sample ({len(report.spot_check_sample)} records) ---")
    for s in report.spot_check_sample:
        print(f"  [{s['record_id'][:8]}...] {s['act_name_en']} s.{s['section_no']}")
        print(f"    Tamil: {s['text_ta_preview'][:80]}...")
        print(f"    Source: {s['source_url']}")
        print(f"    SHA: {s['source_file_sha256']} | Span: {s['raw_span']}")
        print()

    if report.warnings:
        print("--- Warnings ---")
        for w in report.warnings:
            print(f"  ⚠ {w}")

    print("=" * 70)


if __name__ == "__main__":
    report = generate_quality_report()
    print_report(report)
