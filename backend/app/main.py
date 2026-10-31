"""
main.py — TamilNyaya-Bench FastAPI application.

On startup:
1. Creates all DB tables.
2. Validates configured models against Groq's live list.
3. Logs the result to the audit log.
4. If GROQ_API_KEY is missing, starts in degraded mode with a visible banner.

Global exception handler: never returns a stack trace to the client.
Every error response is {error, detail}.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .db import create_all_tables
from . import audit as audit_mod
from .llm.groq_client import verify_model_availability


# ── Startup / shutdown ────────────────────────────────────────────────────────

startup_status: dict[str, Any] = {
    "started_at": None,
    "llm_enabled": False,
    "llm_disabled_reason": "",
    "models_available": {},
    "kb_record_count": 0,
    "integrity_status": "not_run",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────────────────
    startup_status["started_at"] = datetime.now(timezone.utc).isoformat()

    # 1. Create DB tables
    create_all_tables()
    audit_mod.log("startup", "Database tables created / verified")

    # 2. Check LLM
    startup_status["llm_enabled"] = settings.llm_enabled
    startup_status["llm_disabled_reason"] = settings.llm_disabled_reason

    if settings.llm_enabled:
        model_checks: dict[str, bool] = {}
        for attr, label in [
            ("groq_model_under_test", "model_under_test"),
            ("groq_model_judge", "model_judge"),
            ("groq_model_nli", "model_nli"),
        ]:
            model_name = getattr(settings, attr)
            available, all_models = verify_model_availability(model_name)
            model_checks[label] = available
            if not available:
                audit_mod.log(
                    action="startup_model_unavailable",
                    detail=(
                        f"Configured model '{model_name}' ({label}) is NOT in Groq's "
                        f"live model list. Available: {all_models[:5]}…"
                    ),
                    level=audit_mod.AuditLevel.WARNING,
                )
            else:
                audit_mod.log(
                    action="startup_model_ok",
                    detail=f"Model '{model_name}' ({label}) confirmed available",
                )
        startup_status["models_available"] = model_checks
    else:
        audit_mod.log(
            action="startup_llm_disabled",
            detail=settings.llm_disabled_reason,
            level=audit_mod.AuditLevel.WARNING,
        )

    # 3. Count KB records
    from .db import KBRecord, get_db_session
    with get_db_session() as session:
        startup_status["kb_record_count"] = session.query(KBRecord).count()

    audit_mod.log(
        action="startup_complete",
        detail=f"App started. KB records: {startup_status['kb_record_count']}. LLM: {settings.llm_enabled}",
    )

    yield  # ── App running ──────────────────────────────────────────────────

    audit_mod.log("shutdown", "Application shutting down")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="TamilNyaya-Bench API",
    description=(
        "Research prototype — not legal advice. "
        "All evaluated models are general-purpose models, not fine-tuned for Tamil law."
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# CORS: allow Next.js on localhost, Vercel deployments, and optional custom domains
import os

cors_env = os.environ.get("CORS_ORIGINS", "")
custom_origins = [o.strip() for o in cors_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        *custom_origins,
    ],
    allow_origin_regex=r"^https://.*\.vercel\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Global exception handler ──────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch all unhandled exceptions.  Log them; never return a stack trace.
    """
    audit_mod.log_error(
        action="unhandled_exception",
        detail=f"{type(exc).__name__}: {exc}",
        exc=exc,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "detail": (
                "An unexpected error occurred.  It has been recorded in the audit log. "
                "No stack trace is returned to protect system internals."
            ),
        },
    )


# ── Include routers ───────────────────────────────────────────────────────────

from .api import health, kb, items, runs, verification, leaderboard, annotation, audit_router

app.include_router(health.router, prefix="/api")
app.include_router(kb.router, prefix="/api/kb", tags=["Knowledge Base"])
app.include_router(items.router, prefix="/api", tags=["Benchmark Items"])
app.include_router(runs.router, prefix="/api", tags=["Evaluation Runs"])
app.include_router(verification.router, prefix="/api", tags=["Verification"])
app.include_router(leaderboard.router, prefix="/api", tags=["Leaderboard"])
app.include_router(annotation.router, prefix="/api", tags=["Annotation"])
app.include_router(audit_router.router, prefix="/api", tags=["Audit"])


# ── Root ──────────────────────────────────────────────────────────────────────

@app.get("/", tags=["Root"])
async def root() -> dict:
    return {
        "project": "TamilNyaya-Bench",
        "version": "0.1.0",
        "description": (
            "Research prototype. Not legal advice. "
            "Evaluated models are general-purpose models, not fine-tuned for Tamil law."
        ),
        "api_docs": "/api/docs",
        "health": "/api/health",
    }
