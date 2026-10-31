"""
verification.py — Live Check and per-item verification API.

POST /api/check — paste a question + answer and run all three layers
GET  /api/metrics/{name}/explain — explain a metric formula
GET  /api/leaderboard-metrics — computed metrics for all models
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import settings
from ..verification.citation_verifier import verify_citations, CitationVerificationResult
from ..verification.taxonomy import TAXONOMY, TAXONOMY_VERSION

router = APIRouter()


class LiveCheckRequest(BaseModel):
    question: str
    answer: str
    required_jurisdiction: Optional[str] = None    # "Central" | "Tamil Nadu" | None
    run_faithfulness: bool = True
    run_judge: bool = True


class CitationVerdictOut(BaseModel):
    raw_text: str
    char_start: int
    char_end: int
    pattern_name: str
    normalized_section: str
    verdict: str
    branch_fired: str
    severity: int
    matched_record_id: Optional[str]
    matched_act_name: Optional[str]
    fuzzy_score: Optional[float]
    fuzzy_threshold: int
    lookup_description: str
    kb_has_complete_coverage: Optional[bool]


class LiveCheckResponse(BaseModel):
    question: str
    answer: str
    layer1: dict
    layer2: Optional[dict]
    layer3: Optional[dict]
    llm_enabled: bool
    llm_disabled_reason: str


@router.post("/check", response_model=LiveCheckResponse)
async def live_check(req: LiveCheckRequest) -> LiveCheckResponse:
    """
    Run the three verification layers on a user-supplied question + answer.
    Layer 1 is always run (deterministic).
    Layers 2 and 3 require LLM to be enabled.
    """
    # Layer 1 — always
    l1 = verify_citations(req.answer, required_jurisdiction=req.required_jurisdiction)

    l1_out = {
        "total_citations": l1.total_citations,
        "correct_citations": l1.correct_citations,
        "verdicts": [
            {
                "raw_text": v.extracted.raw_text,
                "char_start": v.extracted.char_start,
                "char_end": v.extracted.char_end,
                "pattern_name": v.extracted.pattern_name,
                "normalized_section": v.extracted.normalized_section,
                "verdict": v.verdict.value if v.verdict else "CORRECT",
                "branch_fired": v.branch_fired,
                "severity": v.severity,
                "matched_record_id": v.matched_record_id,
                "matched_act_name": v.matched_act_name,
                "fuzzy_score": v.fuzzy_score,
                "fuzzy_threshold": v.fuzzy_threshold,
                "lookup_description": v.lookup_description,
                "kb_has_complete_coverage": v.kb_has_complete_coverage,
                "is_correct": v.is_correct,
            }
            for v in l1.verdicts
        ],
        "error": l1.error,
    }

    l2_out: Optional[dict] = None
    l3_out: Optional[dict] = None

    if not settings.llm_enabled:
        return LiveCheckResponse(
            question=req.question,
            answer=req.answer,
            layer1=l1_out,
            layer2=None,
            layer3=None,
            llm_enabled=False,
            llm_disabled_reason=settings.llm_disabled_reason,
        )

    # Layer 2 — faithfulness (needs a source passage)
    if req.run_faithfulness:
        from ..llm.nli_backend import GroqNLIBackend
        try:
            nli = GroqNLIBackend()
            # Use the question itself as the "source" for live check
            # (in a real run, the source passage comes from the KB record)
            faith = nli.check_faithfulness(
                source_passage=f"[Live Check — no KB source passage provided. Question: {req.question}]",
                model_answer=req.answer,
            )
            l2_out = {
                "faithfulness_score": faith.faithfulness_score,
                "total_claims": faith.total_claims,
                "entailed_count": faith.entailed_count,
                "neutral_count": faith.neutral_count,
                "contradicted_count": faith.contradicted_count,
                "claims": [
                    {
                        "claim_text": c.claim_text,
                        "label": c.label.value,
                        "supporting_sentence": c.supporting_sentence,
                        "nli_prompt": c.nli_prompt,
                        "nli_raw_response": c.nli_raw_response,
                    }
                    for c in faith.claims
                ],
                "note": "Source passage is not available in Live Check — NLI results are illustrative only",
            }
        except Exception as exc:
            l2_out = {"error": str(exc)}

    return LiveCheckResponse(
        question=req.question,
        answer=req.answer,
        layer1=l1_out,
        layer2=l2_out,
        layer3=l3_out,
        llm_enabled=settings.llm_enabled,
        llm_disabled_reason="",
    )


@router.get("/metrics/{name}/explain")
async def explain_metric(name: str) -> dict:
    """Return the formula, description and computation method for a named metric."""
    METRICS = {
        "citation_accuracy": {
            "name": "Citation Accuracy",
            "formula": "correct_citations / total_verifiable_citations",
            "description": (
                "Fraction of citations that are correct: Act found, section exists, "
                "jurisdiction matches, provision is in force. "
                "Unverifiable citations (outside KB coverage) are excluded from denominator."
            ),
            "numerator": "Count of CORRECT verdicts from Layer 1",
            "denominator": "Count of verifiable citations (excludes UnverifiableCitation)",
            "null_condition": "Returns n/a when total_verifiable_citations = 0",
            "implementation": "pipeline/aggregator.py::compute_citation_accuracy()",
        },
        "faithfulness_score": {
            "name": "Faithfulness Score",
            "formula": "entailed_claims / total_claims",
            "description": "Mean fraction of atomic claims entailed by the real source passage.",
            "numerator": "Claims labelled ENTAILED by the NLI model",
            "denominator": "All atomic claims extracted from the answer",
            "null_condition": "Returns n/a for non-grounded items (no source passage)",
            "implementation": "llm/nli_backend.py::GroqNLIBackend.check_faithfulness()",
        },
        "severity3_rate": {
            "name": "Severity-3 Hallucination Rate",
            "formula": "count(errors where severity=3) / total_items",
            "description": (
                "Fraction of items with at least one severity-3 error "
                "(CitationFabrication, JurisdictionConflation, ObsoleteLawAsCurrent, "
                "WrongLegalConsequence, InventedPrecedent). Headline risk metric."
            ),
            "numerator": "Items with max_severity = 3",
            "denominator": "All items in the run",
            "null_condition": "Returns 0/0 → n/a when no items in run",
            "implementation": "pipeline/aggregator.py::compute_hallucination_rates()",
        },
        "jurisdiction_confusion": {
            "name": "Jurisdiction Confusion Rate",
            "formula": "count(JurisdictionConflation) / total_jurisdiction_sensitive_items",
            "description": "How often the model confuses Central and Tamil Nadu jurisdiction.",
            "numerator": "Items with a JurisdictionConflation verdict",
            "denominator": "Items tagged as jurisdiction probes",
            "null_condition": "Returns n/a when no jurisdiction_probe items in run",
            "implementation": "pipeline/aggregator.py::compute_jurisdiction_confusion()",
        },
        "adversarial_robustness": {
            "name": "Adversarial Robustness Δ",
            "formula": "accuracy_clean_subset − accuracy_adversarial_subset",
            "description": (
                "Drop in citation accuracy between clean items and adversarial items. "
                "Larger Δ = less robust to traps (wrong Act, repealed law, flipped jurisdiction)."
            ),
            "numerator": "Accuracy on clean items minus accuracy on adversarial items",
            "denominator": "N/a (this is a difference, not a fraction)",
            "null_condition": "Returns n/a when fewer than 1 adversarial item in run",
            "implementation": "pipeline/aggregator.py::compute_adversarial_delta()",
        },
    }

    if name not in METRICS:
        raise HTTPException(
            status_code=404,
            detail={"error": "unknown_metric", "detail": f"Metric '{name}' not defined. Available: {list(METRICS.keys())}"},
        )
    return METRICS[name]


@router.get("/taxonomy")
async def get_taxonomy() -> dict:
    return {
        "version": TAXONOMY_VERSION,
        "categories": [
            {
                "category": k.value,
                "group": v.group.value,
                "severity": v.severity,
                "severity_label": v.severity_label,
                "description": v.description,
                "layer": v.layer,
                "rule_reference": v.rule_reference,
            }
            for k, v in TAXONOMY.items()
        ],
    }
