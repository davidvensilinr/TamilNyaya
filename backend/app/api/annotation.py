"""
annotation.py — Annotation and calibration API.
GET/POST /api/annotations
GET      /api/calibration
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from ..db import Annotation, BenchmarkItem, RunResult, get_db_session
from ..config import settings

router = APIRouter()


class AnnotationIn(BaseModel):
    item_id: str
    run_result_id: Optional[int] = None
    annotator_id: str
    error_categories: list[str]
    severity: int
    notes: Optional[str] = None


class AnnotationOut(BaseModel):
    id: int
    item_id: str
    run_result_id: Optional[int]
    annotator_id: str
    timestamp: datetime
    error_categories: list[str]
    severity: int
    notes: Optional[str]
    is_adjudicated: bool
    adjudicated_by: Optional[str]


class CalibrationRow(BaseModel):
    category: str
    labeled_items: int
    kappa: Optional[float]
    kappa_threshold: float
    status: str     # "calibrated" | "human_review_required" | "insufficient_data" | "not_run"
    note: str


@router.get("/annotations", response_model=list[AnnotationOut])
async def list_annotations(
    item_id: Optional[str] = None,
    annotator_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AnnotationOut]:
    with get_db_session() as session:
        q = session.query(Annotation)
        if item_id:
            q = q.filter_by(item_id=item_id)
        if annotator_id:
            q = q.filter_by(annotator_id=annotator_id)
        rows = q.offset(offset).limit(limit).all()
        return [
            AnnotationOut(
                id=r.id,
                item_id=r.item_id,
                run_result_id=r.run_result_id,
                annotator_id=r.annotator_id,
                timestamp=r.timestamp,
                error_categories=json.loads(r.error_categories),
                severity=r.severity,
                notes=r.notes,
                is_adjudicated=r.is_adjudicated,
                adjudicated_by=r.adjudicated_by,
            )
            for r in rows
        ]


@router.post("/annotations", response_model=AnnotationOut)
async def create_annotation(body: AnnotationIn) -> AnnotationOut:
    with get_db_session() as session:
        # Verify item exists
        item = session.query(BenchmarkItem).filter_by(item_id=body.item_id).first()
        if not item:
            raise HTTPException(status_code=404, detail={"error": "item_not_found"})

        ann = Annotation(
            item_id=body.item_id,
            run_result_id=body.run_result_id,
            annotator_id=body.annotator_id,
            timestamp=datetime.now(timezone.utc),
            error_categories=json.dumps(body.error_categories),
            severity=body.severity,
            notes=body.notes,
            is_adjudicated=False,
        )
        session.add(ann)
        session.commit()
        session.refresh(ann)
        return AnnotationOut(
            id=ann.id,
            item_id=ann.item_id,
            run_result_id=ann.run_result_id,
            annotator_id=ann.annotator_id,
            timestamp=ann.timestamp,
            error_categories=body.error_categories,
            severity=ann.severity,
            notes=ann.notes,
            is_adjudicated=False,
            adjudicated_by=None,
        )


@router.get("/calibration", response_model=list[CalibrationRow])
async def calibration() -> list[CalibrationRow]:
    """
    Compute judge calibration per error category.
    Only computed from REAL human labels (Annotation table).
    Returns honest "insufficient_data" messages when MIN_LABELED_ITEMS not reached.
    """
    from ..annotation.agreement import compute_kappa_per_category
    from ..verification.taxonomy import TAXONOMY, ErrorCategory

    with get_db_session() as session:
        all_annotations = session.query(Annotation).all()

    if not all_annotations:
        return [
            CalibrationRow(
                category=cat.value,
                labeled_items=0,
                kappa=None,
                kappa_threshold=settings.kappa_threshold,
                status="not_run",
                note=(
                    "No human annotations yet. "
                    "Use the Annotation page to label items. "
                    f"Minimum {settings.min_labeled_items_for_calibration} labels required per category "
                    "before calibration is meaningful."
                ),
            )
            for cat in ErrorCategory
            if cat.value != "UnverifiableCitation"
        ]

    kappa_results = compute_kappa_per_category(all_annotations)
    rows = []
    for cat in ErrorCategory:
        if cat.value == "UnverifiableCitation":
            continue
        k_data = kappa_results.get(cat.value, {})
        n = k_data.get("n", 0)
        kappa = k_data.get("kappa")

        if n < settings.min_labeled_items_for_calibration:
            status = "insufficient_data"
            note = (
                f"Only {n} labeled items for this category. "
                f"Need {settings.min_labeled_items_for_calibration} for meaningful calibration."
            )
        elif kappa is not None and kappa >= settings.kappa_threshold:
            status = "calibrated"
            note = f"κ={kappa:.3f} ≥ threshold {settings.kappa_threshold}"
        elif kappa is not None:
            status = "human_review_required"
            note = (
                f"κ={kappa:.3f} < threshold {settings.kappa_threshold}. "
                "LLM judge verdicts for this category are flagged 'human review required'."
            )
        else:
            status = "insufficient_data"
            note = "Could not compute kappa (insufficient paired annotations)."

        rows.append(
            CalibrationRow(
                category=cat.value,
                labeled_items=n,
                kappa=kappa,
                kappa_threshold=settings.kappa_threshold,
                status=status,
                note=note,
            )
        )
    return rows


@router.get("/annotations/export/csv")
async def export_annotations_csv() -> Response:
    with get_db_session() as session:
        anns = session.query(Annotation).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id", "item_id", "run_result_id", "annotator_id", "timestamp",
        "error_categories", "severity", "notes", "is_adjudicated", "adjudicated_by"
    ])
    for a in anns:
        writer.writerow([
            a.id, a.item_id, a.run_result_id or "", a.annotator_id, a.timestamp.isoformat(),
            a.error_categories, a.severity, a.notes or "", a.is_adjudicated, a.adjudicated_by or ""
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=annotations_export.csv"},
    )


@router.post("/annotations/import/csv")
async def import_annotations_csv(file: UploadFile = File(...)) -> dict:
    contents = (await file.read()).decode("utf-8")
    reader = csv.DictReader(io.StringIO(contents))
    inserted = 0
    errors = []

    with get_db_session() as session:
        for idx, row in enumerate(reader, start=1):
            item_id = row.get("item_id", "").strip()
            annotator_id = row.get("annotator_id", "").strip()
            if not item_id or not annotator_id:
                errors.append(f"Row {idx}: missing item_id or annotator_id")
                continue

            item = session.query(BenchmarkItem).filter_by(item_id=item_id).first()
            if not item:
                errors.append(f"Row {idx}: item '{item_id}' not found in benchmark_items")
                continue

            # Check if exists
            existing = session.query(Annotation).filter_by(item_id=item_id, annotator_id=annotator_id).first()
            try:
                cats = row.get("error_categories", "[]")
                # validate json
                json.loads(cats)
            except Exception:
                cats = json.dumps([c.strip() for c in cats.split(";") if c.strip()])

            sev = int(row.get("severity", 0))

            if existing:
                existing.error_categories = cats
                existing.severity = sev
                existing.notes = row.get("notes")
            else:
                ann = Annotation(
                    item_id=item_id,
                    run_result_id=int(row["run_result_id"]) if row.get("run_result_id") else None,
                    annotator_id=annotator_id,
                    timestamp=datetime.now(timezone.utc),
                    error_categories=cats,
                    severity=sev,
                    notes=row.get("notes"),
                    is_adjudicated=row.get("is_adjudicated", "").lower() in ("true", "1"),
                    adjudicated_by=row.get("adjudicated_by") or None,
                )
                session.add(ann)
            inserted += 1

        session.commit()

    return {"inserted_or_updated": inserted, "errors": errors}


@router.get("/annotations/disagreements")
async def list_disagreements() -> list[dict]:
    from collections import defaultdict
    with get_db_session() as session:
        anns = session.query(Annotation).all()

    by_item: dict[str, list[Annotation]] = defaultdict(list)
    for a in anns:
        by_item[a.item_id].append(a)

    disagreements = []
    for item_id, item_anns in by_item.items():
        if len(item_anns) >= 2:
            # Check if categories or severities differ
            cats_set = {tuple(sorted(json.loads(a.error_categories))) for a in item_anns}
            sevs_set = {a.severity for a in item_anns}
            if len(cats_set) > 1 or len(sevs_set) > 1:
                with get_db_session() as session:
                    item = session.query(BenchmarkItem).filter_by(item_id=item_id).first()
                disagreements.append({
                    "item_id": item_id,
                    "task_family": item.task_family if item else "unknown",
                    "annotations": [
                        {
                            "id": a.id,
                            "annotator_id": a.annotator_id,
                            "severity": a.severity,
                            "error_categories": json.loads(a.error_categories),
                            "notes": a.notes,
                            "is_adjudicated": a.is_adjudicated,
                        }
                        for a in item_anns
                    ],
                })

    return disagreements


class AdjudicationIn(BaseModel):
    item_id: str
    adjudicated_by: str
    resolved_error_categories: list[str]
    resolved_severity: int
    resolution_notes: Optional[str] = None


@router.post("/annotations/adjudicate")
async def adjudicate_item(body: AdjudicationIn) -> dict:
    with get_db_session() as session:
        anns = session.query(Annotation).filter_by(item_id=body.item_id).all()
        if not anns:
            raise HTTPException(status_code=404, detail={"error": "no_annotations_for_item"})

        for a in anns:
            a.is_adjudicated = True
            a.adjudicated_by = body.adjudicated_by

        # Save the adjudicated gold label
        adjudicated_ann = Annotation(
            item_id=body.item_id,
            annotator_id=f"adjudicator_{body.adjudicated_by}",
            timestamp=datetime.now(timezone.utc),
            error_categories=json.dumps(body.resolved_error_categories),
            severity=body.resolved_severity,
            notes=body.resolution_notes,
            is_adjudicated=True,
            adjudicated_by=body.adjudicated_by,
        )
        session.add(adjudicated_ann)
        session.commit()

    return {"status": "adjudicated", "item_id": body.item_id}
