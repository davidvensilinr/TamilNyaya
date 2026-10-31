"""
llm_judge.py — Layer 3: LLM Judge.

Evaluates fuzzy categories that database lookups or NLI cannot decide:
- TerminologyMistranslation
- InventedPrecedent
- WrongLegalConsequence

Governing rules:
- The judge never overrides a Layer 1 (Citation Verifier) verdict.
- Every verdict is explicitly marked "LLM-judged, not human-verified"
  unless the category has passed calibration against real human labels.
- Output is strictly validated using Pydantic; one retry on malformed JSON;
  then marked judge_failed = True.
"""

from __future__ import annotations

from typing import Optional

from ..llm.judge_backend import (
    GroqJudgeBackend,
    JudgeBackend,
    JudgeResult,
    JUDGE_CATEGORIES,
)


def get_default_judge_backend() -> JudgeBackend:
    return GroqJudgeBackend()


def evaluate_category(
    category: str,
    question: str,
    gold_answer: str,
    model_answer: str,
    kb_text: str,
    backend: Optional[JudgeBackend] = None,
    run_id: Optional[str] = None,
) -> JudgeResult:
    """
    Query the LLM judge for a specific error category.
    """
    if category not in JUDGE_CATEGORIES:
        raise ValueError(
            f"Category '{category}' is not a Layer 3 judge category. "
            f"Allowed: {sorted(list(JUDGE_CATEGORIES))}"
        )

    judge = backend or get_default_judge_backend()
    return judge.judge(
        category=category,
        question=question,
        gold_answer=gold_answer,
        model_answer=model_answer,
        kb_text=kb_text,
        run_id=run_id,
    )
