"""
kb.py — Knowledge Base API routers.

GET /api/kb/search     — full-text and Act-name search
GET /api/kb/{record_id} — single record with provenance link
GET /api/kb/coverage   — coverage table per Act
GET /api/kb/quality    — data-quality report
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..db import KBRecord, ActCoverage, get_db_session

router = APIRouter()


# ── Pydantic response models ──────────────────────────────────────────────────

class KBRecordOut(BaseModel):
    record_id: str
    act_name_ta: str
    act_name_en: str
    section_no: str
    text_ta: str
    text_en: Optional[str]
    jurisdiction: str
    in_force: Optional[bool]
    repealed_by: Optional[str]
    as_of_date: Optional[str]
    source_url: str
    source_document_title: str
    source_file_sha256: str
    retrieved_at: datetime
    parser_name_and_version: str
    extraction_method: str
    ocr_confidence: Optional[float]
    raw_span: Optional[str]

    class Config:
        from_attributes = True


class CoverageRow(BaseModel):
    act_name_en: str
    jurisdiction: str
    sections_in_source: Optional[int]
    sections_ingested: int
    coverage_pct: Optional[float]
    coverage_note: Optional[str]
    complete: Optional[bool]


class QualityReport(BaseModel):
    total_records: int
    records_with_empty_tamil: int
    records_with_ocr: int
    ocr_confidence_mean: Optional[float]
    ocr_confidence_min: Optional[float]
    duplicate_check_note: str
    rejection_summary: str
    spot_check_sample: list[dict]    # N random records for human spot-check


@router.get("/search", response_model=list[KBRecordOut])
async def search_kb(
    q: str = Query(default="", description="Search in act_name_en, act_name_ta, section_no, text_ta, text_en"),
    jurisdiction: Optional[str] = Query(default=None),
    act_name: Optional[str] = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[KBRecordOut]:
    with get_db_session() as session:
        query = session.query(KBRecord)
        if jurisdiction:
            query = query.filter(KBRecord.jurisdiction == jurisdiction)
        if act_name:
            query = query.filter(
                KBRecord.act_name_en.ilike(f"%{act_name}%")
                | KBRecord.act_name_ta.contains(act_name)
            )
        if q:
            query = query.filter(
                KBRecord.act_name_en.ilike(f"%{q}%")
                | KBRecord.act_name_ta.contains(q)
                | KBRecord.section_no.ilike(f"%{q}%")
                | KBRecord.text_ta.contains(q)
                | KBRecord.text_en.ilike(f"%{q}%")
            )
        records = query.offset(offset).limit(limit).all()
        return [KBRecordOut.model_validate(r) for r in records]


@router.get("/coverage", response_model=list[CoverageRow])
async def kb_coverage() -> list[CoverageRow]:
    with get_db_session() as session:
        rows = session.query(ActCoverage).all()

    result = []
    for r in rows:
        pct: Optional[float] = None
        complete: Optional[bool] = None
        if r.sections_in_source and r.sections_in_source > 0:
            pct = round(r.sections_ingested / r.sections_in_source * 100, 1)
            complete = r.sections_ingested >= r.sections_in_source
        result.append(
            CoverageRow(
                act_name_en=r.act_name_en,
                jurisdiction=r.jurisdiction,
                sections_in_source=r.sections_in_source,
                sections_ingested=r.sections_ingested,
                coverage_pct=pct,
                coverage_note=r.coverage_note,
                complete=complete,
            )
        )
    return result


@router.get("/quality", response_model=QualityReport)
async def kb_quality() -> QualityReport:
    import random

    with get_db_session() as session:
        total = session.query(KBRecord).count()
        empty_ta = session.query(KBRecord).filter(KBRecord.text_ta == "").count()
        ocr_records = session.query(KBRecord).filter(KBRecord.extraction_method == "ocr").all()
        ocr_count = len(ocr_records)
        ocr_conf_mean: Optional[float] = None
        ocr_conf_min: Optional[float] = None
        if ocr_count > 0:
            confs = [r.ocr_confidence for r in ocr_records if r.ocr_confidence is not None]
            if confs:
                ocr_conf_mean = round(sum(confs) / len(confs), 3)
                ocr_conf_min = round(min(confs), 3)

        # Random spot-check sample (5 records)
        all_ids = [r.record_id for r in session.query(KBRecord.record_id).all()]
        sample_ids = random.sample(all_ids, min(5, len(all_ids)))
        spot_records = session.query(KBRecord).filter(KBRecord.record_id.in_(sample_ids)).all()
        spot_sample = [
            {
                "record_id": r.record_id,
                "act_name_en": r.act_name_en,
                "section_no": r.section_no,
                "text_ta_preview": r.text_ta[:200] if r.text_ta else "(empty)",
                "source_url": r.source_url,
                "extraction_method": r.extraction_method,
                "raw_span": r.raw_span,
            }
            for r in spot_records
        ]

    if total == 0:
        return QualityReport(
            total_records=0,
            records_with_empty_tamil=0,
            records_with_ocr=0,
            ocr_confidence_mean=None,
            ocr_confidence_min=None,
            duplicate_check_note="No records ingested yet",
            rejection_summary="No records ingested yet. Run the ingestion pipeline first.",
            spot_check_sample=[],
        )

    return QualityReport(
        total_records=total,
        records_with_empty_tamil=empty_ta,
        records_with_ocr=ocr_count,
        ocr_confidence_mean=ocr_conf_mean,
        ocr_confidence_min=ocr_conf_min,
        duplicate_check_note=(
            "Duplicates are prevented at insert time by UNIQUE(source_file_sha256, section_no)."
        ),
        rejection_summary=(
            "See the audit log for a record of every rejected section and its reason."
        ),
        spot_check_sample=spot_sample,
    )


@router.get("/{record_id}", response_model=KBRecordOut)
async def get_kb_record(record_id: str) -> KBRecordOut:
    with get_db_session() as session:
        record = session.query(KBRecord).filter_by(record_id=record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail={"error": "not_found", "detail": f"KB record '{record_id}' not found"})
    return KBRecordOut.model_validate(record)
