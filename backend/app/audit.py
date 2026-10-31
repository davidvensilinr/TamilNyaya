"""
audit.py — Append-only audit log.

Every significant system action (fetch, parse, ingest, run, verification step,
error, retry) is recorded here.  Records are never deleted or updated.
The UI reads this table to show "every system step with timestamps and outcomes".
"""

from __future__ import annotations

import traceback
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy.orm import Session

from .db import AuditEntry, get_db_session


class AuditLevel(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    RETRY = "RETRY"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def log(
    action: str,
    detail: str,
    level: AuditLevel = AuditLevel.INFO,
    run_id: Optional[str] = None,
    item_id: Optional[str] = None,
    source_url: Optional[str] = None,
    exc: Optional[BaseException] = None,
) -> AuditEntry:
    """
    Append one entry to the audit log and return it.

    Parameters
    ----------
    action  : Short machine-readable verb, e.g. "fetch_robots", "ingest_record".
    detail  : Human-readable description of what happened.
    level   : INFO | WARNING | ERROR | RETRY
    run_id  : If this action belongs to an evaluation run, its UUID.
    item_id : If this action belongs to one benchmark item, its ID.
    source_url : The external URL involved, if any.
    exc     : If an exception occurred, pass it here; the traceback is stored.
    """
    tb_str: Optional[str] = None
    if exc is not None:
        tb_str = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))

    entry = AuditEntry(
        timestamp=_now_utc(),
        level=level.value,
        action=action,
        detail=detail,
        run_id=run_id,
        item_id=item_id,
        source_url=source_url,
        traceback=tb_str,
    )

    with get_db_session() as session:
        session.add(entry)
        session.commit()
        session.refresh(entry)

    return entry


def log_error(
    action: str,
    detail: str,
    exc: Optional[BaseException] = None,
    **kwargs,
) -> AuditEntry:
    return log(action, detail, level=AuditLevel.ERROR, exc=exc, **kwargs)


def log_retry(
    action: str,
    detail: str,
    **kwargs,
) -> AuditEntry:
    return log(action, detail, level=AuditLevel.RETRY, **kwargs)
