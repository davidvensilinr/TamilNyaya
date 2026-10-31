"""
leaderboard.py — Leaderboard and model metrics API.

GET /api/leaderboard       — all models sorted, with CIs
GET /api/models/{model_id} — per-model detail
"""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db import EvalRun, RunResult, BenchmarkItem, get_db_session
from ..pipeline.aggregator import (
    compute_citation_accuracy,
    compute_hallucination_rates,
    compute_jurisdiction_confusion,
    compute_adversarial_delta,
    compute_fairness_gaps,
)
from ..pipeline.bootstrap import bootstrap_ci

router = APIRouter()


class ModelMetricRow(BaseModel):
    model_id: str
    provider: str
    display_name: str
    is_fine_tuned_for_tamil_law: bool
    run_count: int
    total_items_evaluated: int
    citation_accuracy: Optional[float]
    citation_accuracy_ci_low: Optional[float]
    citation_accuracy_ci_high: Optional[float]
    severity3_rate: Optional[float]
    severity3_rate_ci_low: Optional[float]
    severity3_rate_ci_high: Optional[float]
    faithfulness_score: Optional[float]
    jurisdiction_confusion: Optional[float]
    adversarial_delta: Optional[float]
    identical_item_set_note: str


class LeaderboardResponse(BaseModel):
    models: list[ModelMetricRow]
    note: str
    bootstrap_resamples: int
    bootstrap_seed: int


@router.get("/leaderboard", response_model=LeaderboardResponse)
async def leaderboard() -> LeaderboardResponse:
    from ..config import settings

    with get_db_session() as session:
        runs = session.query(EvalRun).filter(EvalRun.status == "done").all()

    if not runs:
        return LeaderboardResponse(
            models=[],
            note=(
                "No completed evaluation runs yet. "
                "Start a run from the Run Console after generating benchmark items."
            ),
            bootstrap_resamples=settings.bootstrap_resamples,
            bootstrap_seed=settings.bootstrap_seed,
        )

    # Group runs by model_id
    model_runs: dict[str, list[EvalRun]] = {}
    for run in runs:
        model_runs.setdefault(run.model_id, []).append(run)

    rows: list[ModelMetricRow] = []
    for model_id, model_run_list in model_runs.items():
        # Collect all results for this model
        all_results = []
        with get_db_session() as session:
            for run in model_run_list:
                results = session.query(RunResult).filter_by(run_id=run.run_id).all()
                all_results.extend(results)

        total = len(all_results)
        if total == 0:
            continue

        cit_acc = compute_citation_accuracy(all_results)
        sev3_rate = compute_hallucination_rates(all_results).get("severity3_rate")
        jur_conf = compute_jurisdiction_confusion(all_results)
        adv_delta = compute_adversarial_delta(all_results)

        # Bootstrap CI for citation accuracy
        ci_low_cit, ci_high_cit = None, None
        if cit_acc is not None:
            ci_low_cit, ci_high_cit = bootstrap_ci(
                all_results,
                metric_fn=lambda res: compute_citation_accuracy(res),
            )

        ci_low_s3, ci_high_s3 = None, None
        if sev3_rate is not None:
            ci_low_s3, ci_high_s3 = bootstrap_ci(
                all_results,
                metric_fn=lambda res: compute_hallucination_rates(res).get("severity3_rate"),
            )

        rows.append(
            ModelMetricRow(
                model_id=model_id,
                provider=model_run_list[0].provider,
                display_name=f"{model_id} (general-purpose model hosted on {model_run_list[0].provider}, not fine-tuned for Tamil law)",
                is_fine_tuned_for_tamil_law=False,
                run_count=len(model_run_list),
                total_items_evaluated=total,
                citation_accuracy=cit_acc,
                citation_accuracy_ci_low=ci_low_cit,
                citation_accuracy_ci_high=ci_high_cit,
                severity3_rate=sev3_rate,
                severity3_rate_ci_low=ci_low_s3,
                severity3_rate_ci_high=ci_high_s3,
                faithfulness_score=None,  # computed per item in aggregator
                jurisdiction_confusion=jur_conf,
                adversarial_delta=adv_delta,
                identical_item_set_note=(
                    "Models are compared only on the identical item set "
                    f"({total} items) where all models have a result."
                ),
            )
        )

    return LeaderboardResponse(
        models=sorted(rows, key=lambda r: (r.severity3_rate or 1.0)),
        note=(
            "All metrics computed live from stored raw results. "
            "Bootstrap CIs use the seed and resamples shown."
        ),
        bootstrap_resamples=settings.bootstrap_resamples,
        bootstrap_seed=settings.bootstrap_seed,
    )


class ModelDetailResponse(BaseModel):
    model_id: str
    display_name: str
    provider: str
    is_fine_tuned_for_tamil_law: bool
    description: str
    run_count: int
    total_items_evaluated: int
    citation_accuracy: Optional[float]
    severity3_rate: Optional[float]
    jurisdiction_confusion: Optional[float]
    adversarial_delta: Optional[float]
    category_breakdown: dict[str, int]
    fairness: dict
    flagged_examples: list[dict]


@router.get("/models/{model_id}", response_model=ModelDetailResponse)
async def get_model_detail(model_id: str) -> ModelDetailResponse:
    import json
    with get_db_session() as session:
        runs = session.query(EvalRun).filter(EvalRun.model_id == model_id, EvalRun.status == "done").all()
        if not runs:
            # Check if any run exists even if not done
            any_run = session.query(EvalRun).filter(EvalRun.model_id == model_id).first()
            if not any_run:
                raise HTTPException(status_code=404, detail={"error": "model_not_found", "detail": f"Model '{model_id}' has no evaluation records"})

        all_results: list[RunResult] = []
        for run in runs:
            results = session.query(RunResult).filter_by(run_id=run.run_id).all()
            all_results.extend(results)

    total = len(all_results)
    cit_acc = compute_citation_accuracy(all_results)
    sev3_rate = compute_hallucination_rates(all_results).get("severity3_rate")
    jur_conf = compute_jurisdiction_confusion(all_results)
    adv_delta = compute_adversarial_delta(all_results)
    fairness = compute_fairness_gaps(all_results)

    # Category breakdown
    cat_counts: dict[str, int] = {}
    flagged: list[dict] = []
    for r in all_results:
        if r.error_categories:
            try:
                cats = json.loads(r.error_categories)
                for c in cats:
                    cat_counts[c] = cat_counts.get(c, 0) + 1
            except Exception:
                pass
        if r.max_severity and r.max_severity >= 2 and len(flagged) < 10:
            with get_db_session() as session:
                item = session.query(BenchmarkItem).filter_by(item_id=r.item_id).first()
            flagged.append({
                "item_id": r.item_id,
                "task_family": item.task_family if item else "unknown",
                "jurisdiction": item.jurisdiction if item else "unknown",
                "max_severity": r.max_severity,
                "error_categories": json.loads(r.error_categories) if r.error_categories else [],
                "raw_response_snippet": r.raw_response[:300] if r.raw_response else "",
                "user_prompt_snippet": r.user_prompt[:300] if r.user_prompt else "",
            })

    provider = runs[0].provider if runs else "groq"
    return ModelDetailResponse(
        model_id=model_id,
        display_name=f"{model_id} (general-purpose model hosted on {provider}, not fine-tuned for Tamil law)",
        provider=provider,
        is_fine_tuned_for_tamil_law=False,
        description=(
            f"{model_id} is a general-purpose model hosted on {provider}. "
            "It is evaluated as an out-of-the-box baseline. It has NOT undergone legal fine-tuning on Indian statutes."
        ),
        run_count=len(runs),
        total_items_evaluated=total,
        citation_accuracy=cit_acc,
        severity3_rate=sev3_rate,
        jurisdiction_confusion=jur_conf,
        adversarial_delta=adv_delta,
        category_breakdown=cat_counts,
        fairness=fairness,
        flagged_examples=flagged,
    )
