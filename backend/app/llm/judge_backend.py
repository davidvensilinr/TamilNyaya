"""
judge_backend.py — LLM-Judge interface (Layer 3 verification).

Rules enforced here:
- The judge is ONLY used for categories a database or NLI cannot decide:
  TerminologyMistranslation, InventedPrecedent, WrongLegalConsequence.
- The judge NEVER overrides a Layer 1 (citation verifier) verdict.
- Every verdict is labelled "LLM-judged, not human-verified" until the
  category passes calibration (kappa >= KAPPA_THRESHOLD).
- Malformed JSON responses trigger one retry, then judge_failed = True.
- Pydantic validates the JSON output structure.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from pydantic import BaseModel, ValidationError

from ..config import settings


# ── Allowed judge categories (Layer 3 ONLY) ───────────────────────────────────
JUDGE_CATEGORIES = frozenset([
    "TerminologyMistranslation",
    "InventedPrecedent",
    "WrongLegalConsequence",
])

# ── Pydantic schema for the judge's JSON output ───────────────────────────────

class JudgeOutput(BaseModel):
    category: str
    present: bool
    severity: int                    # 1, 2, or 3
    rationale: str

    class Config:
        extra = "ignore"


@dataclass
class JudgeResult:
    category: str
    present: bool
    severity: int
    rationale: str
    judge_prompt: str
    judge_raw_response: str
    judge_failed: bool = False       # True if JSON parse failed after retry
    failure_reason: Optional[str] = None
    human_verified: bool = False     # set by calibration module
    calibration_status: str = "not_calibrated"  # not_calibrated | calibrated | insufficient_data


class JudgeBackend(ABC):
    @abstractmethod
    def judge(
        self,
        category: str,
        question: str,
        gold_answer: str,
        model_answer: str,
        kb_text: str,
        run_id: Optional[str] = None,
    ) -> JudgeResult:
        """
        Ask the judge whether `category` error is present in model_answer.
        Must return full prompt and raw response.
        """
        ...


# ── Prompt templates ──────────────────────────────────────────────────────────

_JUDGE_SYSTEM = (
    "You are a strict Tamil legal evaluation judge. "
    "Your job is to decide whether a specific error category is present in a model answer. "
    "You must return ONLY a JSON object with exactly these keys: "
    '"category" (string), "present" (boolean), "severity" (integer 1, 2 or 3), '
    '"rationale" (one sentence). '
    "Do not add any text outside the JSON object. "
    "Severity scale: 1=cosmetic, 2=misleading, 3=dangerous if acted on.\n\n"
    "CATEGORY DEFINITIONS:\n"
    "- TerminologyMistranslation: A Tamil legal term is used with the wrong meaning or mistranslated.\n"
    "- InventedPrecedent: A court case or legal precedent is cited that does not exist.\n"
    "- WrongLegalConsequence: The stated penalty, procedure or right is incorrect under the cited law.\n\n"
    "IMPORTANT: Layer 1 citation verdicts (fabrication, misattribution, etc.) are already handled "
    "by a deterministic verifier. Do NOT re-decide those here."
)

_JUDGE_USER = (
    "QUESTION:\n{question}\n\n"
    "GOLD ANSWER (from real KB record):\n{gold_answer}\n\n"
    "MODEL ANSWER (verbatim, unedited):\n{model_answer}\n\n"
    "RELEVANT KB TEXT:\n{kb_text}\n\n"
    "ERROR CATEGORY TO EVALUATE:\n{category}\n\n"
    'Return the JSON object with keys "category", "present", "severity", "rationale".'
)


class GroqJudgeBackend(JudgeBackend):
    def judge(
        self,
        category: str,
        question: str,
        gold_answer: str,
        model_answer: str,
        kb_text: str,
        run_id: Optional[str] = None,
    ) -> JudgeResult:
        from .groq_client import chat_completion, LLMDisabledError

        if category not in JUDGE_CATEGORIES:
            raise ValueError(
                f"Category '{category}' is not a Layer 3 judge category. "
                f"Allowed: {JUDGE_CATEGORIES}"
            )

        if not settings.llm_enabled:
            raise LLMDisabledError(settings.llm_disabled_reason)

        prompt = _JUDGE_USER.format(
            question=question,
            gold_answer=gold_answer,
            model_answer=model_answer,
            kb_text=kb_text,
            category=category,
        )

        messages = [
            {"role": "system", "content": _JUDGE_SYSTEM},
            {"role": "user", "content": prompt},
        ]

        def _attempt() -> tuple[str, Optional[JudgeOutput]]:
            resp = chat_completion(
                messages=messages,
                model=settings.groq_model_judge,
                temperature=0.0,
                max_tokens=256,
                run_id=run_id,
            )
            raw = resp.content.strip()
            try:
                parsed = JudgeOutput.model_validate(json.loads(raw))
                return raw, parsed
            except (json.JSONDecodeError, ValidationError):
                return raw, None

        raw1, parsed1 = _attempt()
        if parsed1 is not None:
            return JudgeResult(
                category=parsed1.category,
                present=parsed1.present,
                severity=parsed1.severity,
                rationale=parsed1.rationale,
                judge_prompt=prompt,
                judge_raw_response=raw1,
            )

        # One retry
        raw2, parsed2 = _attempt()
        if parsed2 is not None:
            return JudgeResult(
                category=parsed2.category,
                present=parsed2.present,
                severity=parsed2.severity,
                rationale=parsed2.rationale,
                judge_prompt=prompt,
                judge_raw_response=raw2,
            )

        return JudgeResult(
            category=category,
            present=False,
            severity=0,
            rationale="",
            judge_prompt=prompt,
            judge_raw_response=raw2,
            judge_failed=True,
            failure_reason="JSON parse failed after 2 attempts",
        )
