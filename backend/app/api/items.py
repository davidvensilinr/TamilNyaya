"""
items.py — Benchmark items API router.

GET /api/items          — filtered list
GET /api/items/{id}     — single item with full provenance
GET /api/dataset/stats  — statistics computed from actual data
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..db import BenchmarkItem, get_db_session

router = APIRouter()


class BenchmarkItemOut(BaseModel):
    item_id: str
    task_family: str
    template_name: str
    template_version: str
    generator_script: str
    primary_source_record_id: str
    all_source_record_ids: str         # JSON array
    gold_answer: Optional[str]
    gold_derivation: Optional[str]
    gold_status: str
    jurisdiction: str
    topic_tag: str
    is_adversarial: bool
    adversarial_perturbation: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class DatasetStats(BaseModel):
    total_items: int
    by_task_family: dict[str, int]
    by_jurisdiction: dict[str, int]
    by_topic_tag: dict[str, int]
    adversarial_count: int
    needs_human_annotation_count: int
    derived_gold_count: int
    human_labeled_count: int
    note: str


@router.get("/items", response_model=list[BenchmarkItemOut])
async def list_items(
    task_family: Optional[str] = Query(default=None),
    jurisdiction: Optional[str] = Query(default=None),
    topic_tag: Optional[str] = Query(default=None),
    is_adversarial: Optional[bool] = Query(default=None),
    gold_status: Optional[str] = Query(default=None),
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[BenchmarkItemOut]:
    with get_db_session() as session:
        q = session.query(BenchmarkItem)
        if task_family:
            q = q.filter(BenchmarkItem.task_family == task_family)
        if jurisdiction:
            q = q.filter(BenchmarkItem.jurisdiction == jurisdiction)
        if topic_tag:
            q = q.filter(BenchmarkItem.topic_tag == topic_tag)
        if is_adversarial is not None:
            q = q.filter(BenchmarkItem.is_adversarial == is_adversarial)
        if gold_status:
            q = q.filter(BenchmarkItem.gold_status == gold_status)
        items = q.offset(offset).limit(limit).all()
        return [BenchmarkItemOut.model_validate(i) for i in items]


@router.get("/dataset/stats", response_model=DatasetStats)
async def dataset_stats() -> DatasetStats:
    from sqlalchemy import func

    with get_db_session() as session:
        total = session.query(BenchmarkItem).count()

        if total == 0:
            return DatasetStats(
                total_items=0,
                by_task_family={},
                by_jurisdiction={},
                by_topic_tag={},
                adversarial_count=0,
                needs_human_annotation_count=0,
                derived_gold_count=0,
                human_labeled_count=0,
                note=(
                    "No benchmark items generated yet. "
                    "Run the item generator after ingesting KB records."
                ),
            )

        by_family = dict(
            session.query(BenchmarkItem.task_family, func.count())
            .group_by(BenchmarkItem.task_family)
            .all()
        )
        by_jur = dict(
            session.query(BenchmarkItem.jurisdiction, func.count())
            .group_by(BenchmarkItem.jurisdiction)
            .all()
        )
        by_topic = dict(
            session.query(BenchmarkItem.topic_tag, func.count())
            .group_by(BenchmarkItem.topic_tag)
            .all()
        )
        adv = session.query(BenchmarkItem).filter_by(is_adversarial=True).count()
        needs_ann = session.query(BenchmarkItem).filter_by(gold_status="needs_human_annotation").count()
        derived = session.query(BenchmarkItem).filter_by(gold_status="derived").count()
        human = session.query(BenchmarkItem).filter_by(gold_status="human_labeled").count()

    return DatasetStats(
        total_items=total,
        by_task_family=by_family,
        by_jurisdiction=by_jur,
        by_topic_tag=by_topic,
        adversarial_count=adv,
        needs_human_annotation_count=needs_ann,
        derived_gold_count=derived,
        human_labeled_count=human,
        note="All counts computed live from the benchmark_items table.",
    )


@router.get("/items/{item_id}", response_model=BenchmarkItemOut)
async def get_item(item_id: str) -> BenchmarkItemOut:
    with get_db_session() as session:
        item = session.query(BenchmarkItem).filter_by(item_id=item_id).first()
    if not item:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "detail": f"Item '{item_id}' not found"},
        )
    return BenchmarkItemOut.model_validate(item)


@router.post("/items/generate")
async def generate_items(seed: int = 42) -> dict:
    """Generate benchmark items from real KB records."""
    from ..items.generator import generate_all_items
    result = generate_all_items(seed=seed)
    return {
        "total_generated": result.total_generated,
        "by_family": result.by_family,
        "skipped": len(result.skipped),
        "errors": result.errors,
    }
