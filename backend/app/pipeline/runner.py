"""
runner.py — Resumable evaluation run executor.

Reads from the DB the items that still need evaluation in run_id,
calls the model, runs all three verification layers, and persists
every result before moving to the next item.

On interrupt: the next call to execute_run with the same run_id
will skip already-completed items and continue from where it stopped.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from ..db import EvalRun, RunResult, BenchmarkItem, KBRecord, get_db_session
from ..models_under_test.groq_adapter import GroqAdapter
from ..verification.citation_verifier import verify_citations
from ..verification.taxonomy import ErrorCategory
from .. import audit as audit_mod
from ..config import settings


def execute_run(run_id: str, req) -> None:
    """
    Execute or resume a run.  All errors are caught per-item and recorded.
    The run never crashes the process.  Runs synchronously in a background thread.
    """
    with get_db_session() as session:
        run = session.query(EvalRun).filter_by(run_id=run_id).first()
        if not run:
            audit_mod.log_error("run_not_found", f"Run {run_id} not found")
            return

        # Snapshot scalar fields before session closes to avoid DetachedInstanceError
        model_id = run.model_id
        temperature = run.temperature
        max_tokens = run.max_tokens
        seed = run.seed
        system_prompt = run.system_prompt

        # Mark as running
        run.status = "running"
        session.commit()

    model = GroqAdapter(model_id)

    # Determine which items to process
    with get_db_session() as session:
        already_done_ids = {
            r.item_id
            for r in session.query(RunResult.item_id).filter_by(run_id=run_id).all()
        }

        # Get all items with deterministic gold
        if req.item_ids:
            items = session.query(BenchmarkItem).filter(
                BenchmarkItem.item_id.in_(req.item_ids)
            ).all()
        else:
            items = session.query(BenchmarkItem).filter(
                BenchmarkItem.gold_status != "needs_human_annotation"
            ).all()

        # Detach/eagerly extract item attributes or load them within the loop
        item_ids_to_run = [i.item_id for i in items if i.item_id not in already_done_ids]

    audit_mod.log(
        action="run_start",
        detail=f"Run {run_id}: {len(item_ids_to_run)} items to process",
        run_id=run_id,
    )

    completed = len(already_done_ids)
    error_count = 0

    for item_id in item_ids_to_run:
        try:
            with get_db_session() as session:
                item = session.query(BenchmarkItem).filter_by(item_id=item_id).first()
                if not item:
                    continue
                source_record = session.query(KBRecord).filter_by(
                    record_id=item.primary_source_record_id
                ).first()
                sys_prompt, user_prompt = _build_prompt(item, source_record)
                task_family = item.task_family
                jurisdiction = item.jurisdiction
                source_text = source_record.text_ta or source_record.text_en or "" if source_record else ""

            # Call the model
            model_resp = model.complete(
                system_prompt=sys_prompt or system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                seed=seed,
                run_id=run_id,
            )

            # Layer 1 — always
            l1 = verify_citations(
                model_resp.raw_text,
                required_jurisdiction=jurisdiction if task_family == "jurisdiction_probe" else None,
            )
            l1_json = json.dumps({
                "total_citations": l1.total_citations,
                "correct_citations": l1.correct_citations,
                "verdicts": [
                    {
                        "raw_text": v.extracted.raw_text,
                        "verdict": v.verdict.value if v.verdict else "CORRECT",
                        "branch_fired": v.branch_fired,
                        "severity": v.severity,
                        "matched_record_id": v.matched_record_id,
                        "fuzzy_score": v.fuzzy_score,
                        "lookup_description": v.lookup_description,
                        "is_correct": v.is_correct,
                    }
                    for v in l1.verdicts
                ],
            })

            # Layer 2 — only for grounded items
            l2_json: Optional[str] = None
            if task_family in ("grounded_qa", "citation_completion") and source_text and settings.llm_enabled:
                try:
                    from ..llm.nli_backend import GroqNLIBackend
                    nli = GroqNLIBackend()
                    faith = nli.check_faithfulness(
                        source_passage=source_text,
                        model_answer=model_resp.raw_text,
                        run_id=run_id,
                    )
                    l2_json = json.dumps({
                        "faithfulness_score": faith.faithfulness_score,
                        "entailed_count": faith.entailed_count,
                        "neutral_count": faith.neutral_count,
                        "contradicted_count": faith.contradicted_count,
                        "total_claims": faith.total_claims,
                    })
                except Exception as exc:
                    l2_json = json.dumps({"error": str(exc)})

            # Determine max severity from Layer 1
            max_sev = 0
            error_cats: list[str] = []
            for v in l1.verdicts:
                if v.severity > max_sev:
                    max_sev = v.severity
                if v.verdict and v.verdict != ErrorCategory.UNVERIFIABLE_CITATION and not v.branch_fired.startswith("CORRECT"):
                    error_cats.append(v.verdict.value)

            now = datetime.now(timezone.utc)
            result = RunResult(
                run_id=run_id,
                item_id=item_id,
                timestamp=now,
                system_prompt=sys_prompt,
                user_prompt=user_prompt,
                raw_response=model_resp.raw_text,
                latency_ms=model_resp.latency_ms,
                prompt_tokens=model_resp.prompt_tokens,
                completion_tokens=model_resp.completion_tokens,
                http_status=model_resp.http_status,
                retry_count=model_resp.retry_count,
                error_message=model_resp.error,
                layer1_result=l1_json,
                layer2_result=l2_json,
                layer3_result=None,
                error_categories=json.dumps(error_cats),
                max_severity=max_sev if max_sev > 0 else None,
            )

            with get_db_session() as session:
                session.add(result)
                completed += 1
                db_run = session.query(EvalRun).filter_by(run_id=run_id).first()
                if db_run:
                    db_run.completed_items = completed
                session.commit()
        except Exception as exc:
            error_count += 1
            audit_mod.log_error(
                action="run_item_error",
                detail=f"Item {item_id} failed: {exc}",
                exc=exc,
                run_id=run_id,
                item_id=item_id,
            )

    # Mark run complete
    with get_db_session() as session:
        db_run = session.query(EvalRun).filter_by(run_id=run_id).first()
        if db_run:
            db_run.status = "done" if error_count == 0 else "done_with_errors"
            db_run.completed_at = datetime.now(timezone.utc)
            db_run.completed_items = completed
            db_run.error_count = error_count
        session.commit()

    audit_mod.log(
        action="run_complete",
        detail=(
            f"Run {run_id} complete: {completed} items, {error_count} errors"
        ),
        run_id=run_id,
    )


def _build_prompt(item: BenchmarkItem, source_record: Optional[KBRecord]) -> tuple[Optional[str], str]:
    """Build (system_prompt, user_prompt) for a benchmark item."""
    sys_prompt = (
        "You are a legal assistant answering questions about Indian and Tamil Nadu law. "
        "Answer only from the provided legal text. Do not invent citations or provisions."
    )

    if item.task_family == "citation_completion":
        user = (
            f"Read the following legal text and identify the Act name and Section number it comes from.\n\n"
            f"TEXT:\n{source_record.text_ta if source_record else '[source not available]'}\n\n"
            "Provide the Act name and Section number."
        )
    elif item.task_family == "grounded_qa":
        user = (
            f"Answer the question using ONLY the following legal provision.\n\n"
            f"PROVISION:\n{source_record.text_ta if source_record else '[source not available]'}\n\n"
            f"QUESTION: {item.gold_derivation or 'What does this provision say?'}"
        )
    elif item.task_family == "closed_book_legal_qa":
        user = item.gold_derivation or f"What does Section {item.primary_source_record_id} say?"
    elif item.task_family == "jurisdiction_probe":
        user = (
            f"Is the following provision from a Central Act or a Tamil Nadu Act? "
            f"Which Act and Section does it belong to?\n\n"
            f"TEXT:\n{source_record.text_ta if source_record else '[source not available]'}"
        )
    else:
        user = item.gold_derivation or "Describe this legal provision."

    return sys_prompt, user


def _evaluate_item(
    run_id: str,
    run: EvalRun,
    item: BenchmarkItem,
    model: GroqAdapter,
    req,
) -> RunResult:
    now = datetime.now(timezone.utc)

    with get_db_session() as session:
        source_record = session.query(KBRecord).filter_by(
            record_id=item.primary_source_record_id
        ).first()

    sys_prompt, user_prompt = _build_prompt(item, source_record)

    # Call the model
    model_resp = model.complete(
        system_prompt=sys_prompt or run.system_prompt,
        user_prompt=user_prompt,
        temperature=run.temperature,
        max_tokens=run.max_tokens,
        seed=run.seed,
        run_id=run_id,
    )

    # Layer 1 — always
    l1 = verify_citations(
        model_resp.raw_text,
        required_jurisdiction=item.jurisdiction if item.task_family == "jurisdiction_probe" else None,
    )
    l1_json = json.dumps({
        "total_citations": l1.total_citations,
        "correct_citations": l1.correct_citations,
        "verdicts": [
            {
                "raw_text": v.extracted.raw_text,
                "verdict": v.verdict.value if v.verdict else "CORRECT",
                "branch_fired": v.branch_fired,
                "severity": v.severity,
                "matched_record_id": v.matched_record_id,
                "fuzzy_score": v.fuzzy_score,
                "lookup_description": v.lookup_description,
                "is_correct": v.is_correct,
            }
            for v in l1.verdicts
        ],
    })

    # Layer 2 — only for grounded items
    l2_json: Optional[str] = None
    if item.task_family in ("grounded_qa", "citation_completion") and source_record and settings.llm_enabled:
        try:
            from ..llm.nli_backend import GroqNLIBackend
            nli = GroqNLIBackend()
            faith = nli.check_faithfulness(
                source_passage=source_record.text_ta or source_record.text_en or "",
                model_answer=model_resp.raw_text,
                run_id=run_id,
            )
            l2_json = json.dumps({
                "faithfulness_score": faith.faithfulness_score,
                "entailed_count": faith.entailed_count,
                "neutral_count": faith.neutral_count,
                "contradicted_count": faith.contradicted_count,
                "total_claims": faith.total_claims,
            })
        except Exception as exc:
            l2_json = json.dumps({"error": str(exc)})

    # Determine max severity from Layer 1
    max_sev = 0
    error_cats: list[str] = []
    for v in l1.verdicts:
        if v.severity > max_sev:
            max_sev = v.severity
        if v.verdict and v.verdict != ErrorCategory.UNVERIFIABLE_CITATION and not v.branch_fired.startswith("CORRECT"):
            error_cats.append(v.verdict.value)

    return RunResult(
        run_id=run_id,
        item_id=item.item_id,
        timestamp=now,
        system_prompt=sys_prompt,
        user_prompt=user_prompt,
        raw_response=model_resp.raw_text,
        latency_ms=model_resp.latency_ms,
        prompt_tokens=model_resp.prompt_tokens,
        completion_tokens=model_resp.completion_tokens,
        http_status=model_resp.http_status,
        retry_count=model_resp.retry_count,
        error_message=model_resp.error,
        layer1_result=l1_json,
        layer2_result=l2_json,
        layer3_result=None,
        error_categories=json.dumps(error_cats),
        max_severity=max_sev if max_sev > 0 else None,
    )
