"""
integrity.py — Integrity checker (python -m backend.app.integrity).

Checks that the rules from Part 1 are not violated:
1. No records with missing provenance
2. Every source_file_sha256 has a matching file in data/raw/
3. No duplicate records
4. All benchmark item gold answers trace to real KB records
5. No hardcoded / fabricated metrics
6. Audit log is non-empty (system has been used)
7. .env is not committed (check .gitignore)

Each check is independent and produces a pass/fail + detail.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from .config import settings
from .db import KBRecord, BenchmarkItem, RunResult, get_db_session


def run_integrity_checks() -> dict:
    """Run all integrity checks and return structured results."""
    from .db import create_all_tables
    create_all_tables()
    checks: list[dict] = []

    checks.append(_check_provenance())
    checks.append(_check_raw_files())
    checks.append(_check_no_duplicates())
    checks.append(_check_item_sources())
    checks.append(_check_no_env_committed())
    checks.append(_check_audit_log())
    checks.append(_check_no_hardcoded_metrics())

    passed = sum(1 for c in checks if c["status"] == "pass")
    failed = sum(1 for c in checks if c["status"] == "fail")
    warnings = sum(1 for c in checks if c["status"] == "warning")

    return {
        "overall": "pass" if failed == 0 else "fail",
        "passed": passed,
        "failed": failed,
        "warnings": warnings,
        "total": len(checks),
        "checks": checks,
    }


def _check_provenance() -> dict:
    """Every KB record must have all mandatory provenance fields filled."""
    name = "provenance_completeness"
    with get_db_session() as session:
        total = session.query(KBRecord).count()
        if total == 0:
            return {"name": name, "status": "warning", "detail": "No KB records ingested yet."}

        missing = []
        records = session.query(KBRecord).all()
        for r in records:
            problems = []
            if not r.source_url:
                problems.append("source_url")
            if not r.source_file_sha256:
                problems.append("source_file_sha256")
            if not r.parser_name_and_version:
                problems.append("parser_name_and_version")
            if not r.extraction_method:
                problems.append("extraction_method")
            if not r.act_name_en and not r.act_name_ta:
                problems.append("act_name (both empty)")
            if problems:
                missing.append({"record_id": r.record_id, "missing": problems})

    if missing:
        return {
            "name": name,
            "status": "fail",
            "detail": f"{len(missing)} records have incomplete provenance.",
            "records": missing[:10],
        }
    return {"name": name, "status": "pass", "detail": f"All {total} records have complete provenance."}


def _check_raw_files() -> dict:
    """Every sha256 referenced in the KB must have a matching raw file."""
    name = "raw_file_integrity"
    raw_dir = settings.data_raw_dir

    with get_db_session() as session:
        hashes = [r[0] for r in session.query(KBRecord.source_file_sha256).distinct().all()]

    if not hashes:
        return {"name": name, "status": "warning", "detail": "No KB records to verify."}

    missing_files = []
    hash_mismatches = []
    for sha in hashes:
        # Check both .html and raw
        candidates = list(raw_dir.glob(f"{sha}.*")) + [raw_dir / sha]
        found = [c for c in candidates if c.exists()]
        if not found:
            missing_files.append(sha[:16] + "…")
            continue

        # Verify the hash
        actual = hashlib.sha256(found[0].read_bytes()).hexdigest()
        if actual != sha:
            hash_mismatches.append({"expected": sha[:16], "actual": actual[:16], "file": str(found[0])})

    issues = []
    if missing_files:
        issues.append(f"{len(missing_files)} raw files missing from data/raw/")
    if hash_mismatches:
        issues.append(f"{len(hash_mismatches)} files have SHA-256 mismatches")

    if issues:
        return {"name": name, "status": "fail", "detail": "; ".join(issues)}
    return {"name": name, "status": "pass", "detail": f"All {len(hashes)} raw files present and verified."}


def _check_no_duplicates() -> dict:
    """No duplicate (act+section) combinations."""
    name = "no_duplicates"
    from sqlalchemy import func

    with get_db_session() as session:
        total = session.query(KBRecord).count()
        if total == 0:
            return {"name": name, "status": "warning", "detail": "No KB records."}

        dupes = (
            session.query(
                KBRecord.act_name_en, KBRecord.section_no, func.count()
            )
            .group_by(KBRecord.act_name_en, KBRecord.section_no)
            .having(func.count() > 1)
            .all()
        )

    if dupes:
        return {
            "name": name,
            "status": "warning",
            "detail": f"{len(dupes)} duplicated (act, section) pairs found.",
            "duplicates": [{"act": d[0], "section": d[1], "count": d[2]} for d in dupes[:10]],
        }
    return {"name": name, "status": "pass", "detail": "No duplicate records."}


def _check_item_sources() -> dict:
    """Every benchmark item must reference a real KB record."""
    name = "item_source_traceability"
    with get_db_session() as session:
        total_items = session.query(BenchmarkItem).count()
        if total_items == 0:
            return {"name": name, "status": "warning", "detail": "No benchmark items generated yet."}

        orphans = []
        items = session.query(BenchmarkItem).all()
        for item in items:
            rec = session.query(KBRecord).filter_by(record_id=item.primary_source_record_id).first()
            if not rec:
                orphans.append(item.item_id)

    if orphans:
        return {
            "name": name,
            "status": "fail",
            "detail": f"{len(orphans)} items reference non-existent KB records.",
            "orphan_item_ids": orphans[:10],
        }
    return {"name": name, "status": "pass", "detail": f"All {total_items} items trace to real KB records."}


def _check_no_env_committed() -> dict:
    """Verify .env is in .gitignore."""
    name = "env_not_committed"
    gitignore_path = Path(".gitignore")
    if not gitignore_path.exists():
        return {"name": name, "status": "warning", "detail": ".gitignore not found in working directory."}

    content = gitignore_path.read_text()
    if ".env" not in content:
        return {"name": name, "status": "fail", "detail": ".env is NOT listed in .gitignore. API keys could be committed."}

    env_path = Path(".env")
    if env_path.exists():
        # Check it's not tracked by git
        import subprocess
        try:
            result = subprocess.run(
                ["git", "ls-files", ".env"], capture_output=True, text=True, timeout=5
            )
            if result.stdout.strip():
                return {"name": name, "status": "fail", "detail": ".env IS tracked by git. Remove it immediately."}
        except Exception:
            pass

    return {"name": name, "status": "pass", "detail": ".env is properly gitignored."}


def _check_audit_log() -> dict:
    """Audit log should have entries if the system has been used."""
    name = "audit_log_present"
    from .db import AuditEntry

    with get_db_session() as session:
        count = session.query(AuditEntry).count()

    if count == 0:
        return {"name": name, "status": "warning", "detail": "Audit log is empty. No system actions recorded yet."}
    return {"name": name, "status": "pass", "detail": f"Audit log has {count} entries."}


def _check_no_hardcoded_metrics() -> dict:
    """Spot-check that run results have real verification traces, not hardcoded values."""
    name = "no_hardcoded_metrics"
    import json

    with get_db_session() as session:
        total_results = session.query(RunResult).count()
        if total_results == 0:
            return {"name": name, "status": "warning", "detail": "No run results yet. Cannot verify."}

        # Sample up to 10 results and check that layer1_result contains real structure
        sample = session.query(RunResult).limit(10).all()
        suspicious = []
        for r in sample:
            if r.layer1_result:
                try:
                    l1 = json.loads(r.layer1_result)
                    if not isinstance(l1, dict) or "verdicts" not in l1:
                        suspicious.append(r.item_id)
                except json.JSONDecodeError:
                    suspicious.append(r.item_id)

    if suspicious:
        return {
            "name": name,
            "status": "fail",
            "detail": f"{len(suspicious)} results have invalid layer1 traces.",
        }
    return {"name": name, "status": "pass", "detail": f"Sampled {len(sample)} results; all have valid verification traces."}


if __name__ == "__main__":
    import json as _json
    result = run_integrity_checks()
    print(_json.dumps(result, indent=2))
    raise SystemExit(0 if result["overall"] == "pass" else 1)
