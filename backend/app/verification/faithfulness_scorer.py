"""
faithfulness_scorer.py — Layer 2: Faithfulness Scorer.

Faithfulness scoring (for grounded items only):
1. Splits the model answer into atomic factual claims.
2. For each claim, queries the NLI backend to check whether it is entailed,
   neutral, or contradicted by the real source passage.
3. Faithfulness score = (number of entailed claims) / (total claims).
4. Produces error categories:
   - contradicted -> ContextContradiction (severity 2)
   - neutral -> UnsupportedElaboration (severity 2)
"""

from __future__ import annotations

from typing import Optional

from ..llm.nli_backend import (
    ClaimResult,
    EntailmentLabel,
    FaithfulnessResult,
    GroqNLIBackend,
    NLIBackend,
)


def get_default_nli_backend() -> NLIBackend:
    return GroqNLIBackend()


def score_faithfulness(
    source_passage: str,
    model_answer: str,
    backend: Optional[NLIBackend] = None,
    run_id: Optional[str] = None,
) -> FaithfulnessResult:
    """
    Score the faithfulness of model_answer against source_passage.
    """
    if not model_answer or not model_answer.strip():
        return FaithfulnessResult(
            claims=[],
            faithfulness_score=0.0,
            entailed_count=0,
            neutral_count=0,
            contradicted_count=0,
            total_claims=0,
            source_passage=source_passage,
            model_answer=model_answer,
            error="Empty model answer",
        )

    nli = backend or get_default_nli_backend()
    return nli.check_faithfulness(
        source_passage=source_passage,
        model_answer=model_answer,
        run_id=run_id,
    )
