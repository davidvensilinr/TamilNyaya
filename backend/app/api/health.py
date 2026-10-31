"""
health.py — GET /api/health endpoint.

Returns: key configured, models available, KB record count, integrity status.
Never shows the key value.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from ..config import settings
from ..main import startup_status
from ..db import KBRecord, get_db_session

router = APIRouter()


class HealthResponse(BaseModel):
    status: str                              # "ok" | "degraded"
    api_key_configured: bool
    llm_enabled: bool
    llm_disabled_reason: str
    models: dict[str, bool]                  # model label → available
    kb_record_count: int
    integrity_status: str
    started_at: Optional[str]
    notice: str


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    with get_db_session() as session:
        kb_count = session.query(KBRecord).count()

    api_key_set = bool(
        settings.groq_api_key
        and settings.groq_api_key.strip()
        and settings.groq_api_key != "your_groq_api_key_here"
    )

    overall = "ok" if settings.llm_enabled and kb_count > 0 else "degraded"

    return HealthResponse(
        status=overall,
        api_key_configured=api_key_set,
        llm_enabled=settings.llm_enabled,
        llm_disabled_reason=settings.llm_disabled_reason if not settings.llm_enabled else "",
        models=startup_status.get("models_available", {}),
        kb_record_count=kb_count,
        integrity_status=startup_status.get("integrity_status", "not_run"),
        started_at=startup_status.get("started_at"),
        notice=(
            "Research prototype. Not legal advice. "
            "Evaluated models are general-purpose models, not fine-tuned for Tamil law."
        ),
    )
