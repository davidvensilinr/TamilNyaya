"""
runs.py — Evaluation runs API router.

POST /api/runs           — start a run
GET  /api/runs           — list runs
GET  /api/runs/{id}      — run detail + progress
GET  /api/runs/{id}/bundle — download run export bundle
GET  /api/trace/{run_id}/{item_id} — full verification trace
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..config import settings
from ..db import EvalRun, RunResult, BenchmarkItem, get_db_session

router = APIRouter()


class RunRequest(BaseModel):
    model_id: Optional[str] = None       # defaults to GROQ_MODEL_UNDER_TEST
    temperature: float = 0.0
    max_tokens: int = 512
    seed: Optional[int] = None
    system_prompt: Optional[str] = None
    item_ids: Optional[list[str]] = None  # None = all items


class RunSummary(BaseModel):
    run_id: str
    status: str
    model_id: str
    provider: str
    temperature: float
    max_tokens: int
    started_at: datetime
    completed_at: Optional[datetime]
    total_items: int
    completed_items: int
    error_count: int

    class Config:
        from_attributes = True


class TraceOut(BaseModel):
    run_id: str
    item_id: str
    item: dict
    raw_response: str
    user_prompt: str
    system_prompt: Optional[str]
    latency_ms: Optional[int]
    prompt_tokens: Optional[int]
    completion_tokens: Optional[int]
    http_status: Optional[int]
    retry_count: int
    layer1_result: Optional[dict]
    layer2_result: Optional[dict]
    layer3_result: Optional[dict]
    error_categories: Optional[list]
    max_severity: Optional[int]


@router.post("/runs", response_model=RunSummary)
async def start_run(req: RunRequest, background_tasks: BackgroundTasks) -> RunSummary:
    if not settings.llm_enabled:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "llm_disabled",
                "detail": settings.llm_disabled_reason,
            },
        )

    model_id = req.model_id or settings.groq_model_under_test
    now = datetime.utcnow()

    with get_db_session() as session:
        # Resolve item IDs
        if req.item_ids:
            total = len(req.item_ids)
        else:
            total = session.query(BenchmarkItem).filter(
                BenchmarkItem.gold_status != "needs_human_annotation"
            ).count()

        if total == 0:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "no_items",
                    "detail": (
                        "No benchmark items available to run. "
                        "Generate items first using the item generator."
                    ),
                },
            )

        run = EvalRun(
            started_at=now,
            status="pending",
            model_id=model_id,
            provider="groq",
            temperature=req.temperature,
            max_tokens=req.max_tokens,
            seed=req.seed,
            system_prompt=req.system_prompt,
            config_snapshot=json.dumps(settings.safe_dict()),
            total_items=total,
            completed_items=0,
            error_count=0,
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        run_id = run.run_id

    # Kick off in background
    background_tasks.add_task(_execute_run, run_id, req)

    with get_db_session() as session:
        run = session.query(EvalRun).filter_by(run_id=run_id).first()
        return RunSummary.model_validate(run)


@router.get("/runs", response_model=list[RunSummary])
async def list_runs(limit: int = 50, offset: int = 0) -> list[RunSummary]:
    with get_db_session() as session:
        runs = (
            session.query(EvalRun)
            .order_by(EvalRun.started_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [RunSummary.model_validate(r) for r in runs]


@router.get("/runs/{run_id}", response_model=RunSummary)
async def get_run(run_id: str) -> RunSummary:
    with get_db_session() as session:
        run = session.query(EvalRun).filter_by(run_id=run_id).first()
    if not run:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "detail": f"Run '{run_id}' not found"},
        )
    return RunSummary.model_validate(run)


@router.get("/runs/{run_id}/bundle")
async def download_bundle(run_id: str) -> StreamingResponse:
    """Generate and stream an audit bundle zip."""
    from ..pipeline.export_bundle import build_bundle_stream
    try:
        stream = build_bundle_stream(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"error": "not_found", "detail": str(exc)})
    return StreamingResponse(
        stream,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=bundle_{run_id[:8]}.zip"},
    )


@router.get("/trace/{run_id}/{item_id}", response_model=TraceOut)
async def get_trace(run_id: str, item_id: str) -> TraceOut:
    with get_db_session() as session:
        result = (
            session.query(RunResult)
            .filter_by(run_id=run_id, item_id=item_id)
            .first()
        )
        if not result:
            raise HTTPException(
                status_code=404,
                detail={"error": "not_found", "detail": f"No trace for run={run_id} item={item_id}"},
            )
        item = session.query(BenchmarkItem).filter_by(item_id=item_id).first()
        item_dict = {
            "item_id": item.item_id,
            "task_family": item.task_family,
            "jurisdiction": item.jurisdiction,
            "topic_tag": item.topic_tag,
            "gold_answer": item.gold_answer,
            "gold_status": item.gold_status,
            "is_adversarial": item.is_adversarial,
        } if item else {}

        return TraceOut(
            run_id=result.run_id,
            item_id=result.item_id,
            item=item_dict,
            raw_response=result.raw_response,
            user_prompt=result.user_prompt,
            system_prompt=result.system_prompt,
            latency_ms=result.latency_ms,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            http_status=result.http_status,
            retry_count=result.retry_count,
            layer1_result=json.loads(result.layer1_result) if result.layer1_result else None,
            layer2_result=json.loads(result.layer2_result) if result.layer2_result else None,
            layer3_result=json.loads(result.layer3_result) if result.layer3_result else None,
            error_categories=json.loads(result.error_categories) if result.error_categories else None,
            max_severity=result.max_severity,
        )


# ── Background run executor ────────────────────────────────────────────────────

async def _execute_run(run_id: str, req: RunRequest) -> None:
    """Execute an evaluation run in the background.  Resumable."""
    from ..pipeline.runner import execute_run
    await execute_run(run_id, req)
