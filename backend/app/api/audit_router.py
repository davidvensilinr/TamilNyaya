"""
audit_router.py — Audit log and integrity API.

GET /api/audit        — paginated audit log
GET /api/integrity    — latest integrity check result
GET /api/tests        — test suite pass/fail summary
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from ..db import AuditEntry, get_db_session

router = APIRouter()


class AuditEntryOut(BaseModel):
    id: int
    timestamp: datetime
    level: str
    action: str
    detail: str
    run_id: Optional[str]
    item_id: Optional[str]
    source_url: Optional[str]
    # traceback is NOT returned to the frontend — it may contain sensitive paths

    class Config:
        from_attributes = True


@router.get("/audit", response_model=list[AuditEntryOut])
async def get_audit_log(
    level: Optional[str] = Query(default=None),
    action: Optional[str] = Query(default=None),
    run_id: Optional[str] = Query(default=None),
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[AuditEntryOut]:
    with get_db_session() as session:
        q = session.query(AuditEntry).order_by(AuditEntry.timestamp.desc())
        if level:
            q = q.filter(AuditEntry.level == level.upper())
        if action:
            q = q.filter(AuditEntry.action.ilike(f"%{action}%"))
        if run_id:
            q = q.filter(AuditEntry.run_id == run_id)
        entries = q.offset(offset).limit(limit).all()
        return [AuditEntryOut.model_validate(e) for e in entries]


@router.get("/integrity")
async def integrity_check() -> dict:
    """
    Run the integrity checker and return results.
    This calls backend/app/integrity.py programmatically.
    """
    from ..integrity import run_integrity_checks
    result = run_integrity_checks()
    return result


@router.get("/tests")
async def test_summary() -> dict:
    """
    Return a summary of the last pytest run (if available).
    Actual test execution happens outside the API (via CI or manual run).
    """
    import subprocess, json as _json
    try:
        result = subprocess.run(
            ["python", "-m", "pytest", "tests/", "--tb=no", "-q", "--json-report",
             "--json-report-file=/tmp/tnb_test_report.json"],
            capture_output=True, text=True, timeout=120,
        )
        try:
            with open("/tmp/tnb_test_report.json") as f:
                report = _json.load(f)
            return {
                "passed": report.get("summary", {}).get("passed", 0),
                "failed": report.get("summary", {}).get("failed", 0),
                "errors": report.get("summary", {}).get("error", 0),
                "total": report.get("summary", {}).get("total", 0),
                "exit_code": result.returncode,
                "note": "Run 'pytest tests/' from the backend/ directory for full output",
            }
        except Exception:
            return {
                "note": "Test report not available. Run: cd backend && python -m pytest tests/",
                "stdout_preview": result.stdout[:500] if result.stdout else "",
            }
    except FileNotFoundError:
        return {
            "note": "pytest not found. Install dev dependencies: pip install -e '.[dev]'",
        }
    except Exception as exc:
        return {"error": str(exc), "note": "Could not run tests from API"}
