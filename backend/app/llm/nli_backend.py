"""
nli_backend.py — NLI (Natural Language Inference) backend interface.

The NLIBackend ABC allows swapping the Groq-based NLI implementation for a
local IndicBERT / mBERT model later, without changing any calling code.

Faithfulness scoring (Layer 2) works by splitting an answer into atomic claims
and checking each claim's entailment against the real source passage.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from ..config import settings


class EntailmentLabel(str, Enum):
    ENTAILED = "entailed"
    NEUTRAL = "neutral"
    CONTRADICTED = "contradicted"


@dataclass
class ClaimResult:
    claim_text: str
    label: EntailmentLabel
    supporting_sentence: Optional[str]   # quoted from source passage
    nli_prompt: str
    nli_raw_response: str
    confidence: Optional[float]           # if the backend provides it


@dataclass
class FaithfulnessResult:
    claims: list[ClaimResult]
    faithfulness_score: float             # entailed / total
    entailed_count: int
    neutral_count: int
    contradicted_count: int
    total_claims: int
    source_passage: str
    model_answer: str
    error: Optional[str] = None


class NLIBackend(ABC):
    @abstractmethod
    def check_faithfulness(
        self,
        source_passage: str,
        model_answer: str,
        run_id: Optional[str] = None,
    ) -> FaithfulnessResult:
        """
        Split model_answer into atomic claims and check each against
        source_passage.  Must store and return exact prompts and raw responses.
        """
        ...


# ── Claim splitter ────────────────────────────────────────────────────────────

_SPLIT_SYSTEM = (
    "You are a precise claim-extraction assistant. "
    "Return ONLY a JSON array of short, self-contained factual claim strings. "
    "Do not add commentary or explanations."
)

_SPLIT_USER = (
    "Extract all distinct factual claims from the following text as a JSON array of strings.\n\n"
    "TEXT:\n{text}"
)

# ── NLI system/user prompts ────────────────────────────────────────────────────

_NLI_SYSTEM = (
    "You are an NLI (Natural Language Inference) model for Indian legal text. "
    "Given a SOURCE PASSAGE and a CLAIM, return ONLY a JSON object with keys: "
    '"label" (one of "entailed", "neutral", "contradicted"), '
    '"supporting_sentence" (the sentence from SOURCE that most directly supports or '
    'refutes the claim, or null if none applies), '
    '"rationale" (one sentence explaining your decision). '
    "Do not add any text outside the JSON object."
)

_NLI_USER = (
    "SOURCE PASSAGE:\n{source}\n\n"
    "CLAIM:\n{claim}\n\n"
    'Return the JSON object with keys "label", "supporting_sentence", "rationale".'
)


class GroqNLIBackend(NLIBackend):
    """
    Uses the configured GROQ_MODEL_NLI model via the Groq API.

    Temperature is forced to 0 for determinism.
    If LLM is disabled, check_faithfulness raises LLMDisabledError.
    """

    def check_faithfulness(
        self,
        source_passage: str,
        model_answer: str,
        run_id: Optional[str] = None,
    ) -> FaithfulnessResult:
        from .groq_client import chat_completion, LLMDisabledError

        if not settings.llm_enabled:
            from .groq_client import LLMDisabledError
            raise LLMDisabledError(settings.llm_disabled_reason)

        # Step 1 — Split the answer into atomic claims
        split_response = chat_completion(
            messages=[
                {"role": "system", "content": _SPLIT_SYSTEM},
                {"role": "user", "content": _SPLIT_USER.format(text=model_answer)},
            ],
            model=settings.groq_model_nli,
            temperature=0.0,
            max_tokens=512,
            run_id=run_id,
        )

        try:
            raw_claims = json.loads(split_response.content)
            if not isinstance(raw_claims, list):
                raise ValueError("Expected JSON array")
            claims_list: list[str] = [str(c) for c in raw_claims if c]
        except Exception:
            claims_list = [model_answer.strip()]  # fallback: treat whole answer as one claim

        if not claims_list:
            return FaithfulnessResult(
                claims=[],
                faithfulness_score=0.0,
                entailed_count=0,
                neutral_count=0,
                contradicted_count=0,
                total_claims=0,
                source_passage=source_passage,
                model_answer=model_answer,
                error="No claims extracted",
            )

        # Step 2 — NLI check per claim
        claim_results: list[ClaimResult] = []
        for claim_text in claims_list:
            nli_prompt = _NLI_USER.format(source=source_passage, claim=claim_text)
            nli_response = chat_completion(
                messages=[
                    {"role": "system", "content": _NLI_SYSTEM},
                    {"role": "user", "content": nli_prompt},
                ],
                model=settings.groq_model_nli,
                temperature=0.0,
                max_tokens=256,
                run_id=run_id,
            )

            raw_resp = nli_response.content.strip()
            label = EntailmentLabel.NEUTRAL
            supporting = None
            try:
                parsed = json.loads(raw_resp)
                raw_label = parsed.get("label", "neutral").lower()
                label = EntailmentLabel(raw_label) if raw_label in EntailmentLabel._value2member_map_ else EntailmentLabel.NEUTRAL
                supporting = parsed.get("supporting_sentence")
            except Exception:
                pass  # label stays NEUTRAL on parse failure

            claim_results.append(
                ClaimResult(
                    claim_text=claim_text,
                    label=label,
                    supporting_sentence=supporting,
                    nli_prompt=nli_prompt,
                    nli_raw_response=raw_resp,
                    confidence=None,
                )
            )

        entailed = sum(1 for c in claim_results if c.label == EntailmentLabel.ENTAILED)
        neutral = sum(1 for c in claim_results if c.label == EntailmentLabel.NEUTRAL)
        contradicted = sum(1 for c in claim_results if c.label == EntailmentLabel.CONTRADICTED)
        total = len(claim_results)
        score = entailed / total if total > 0 else 0.0

        return FaithfulnessResult(
            claims=claim_results,
            faithfulness_score=round(score, 4),
            entailed_count=entailed,
            neutral_count=neutral,
            contradicted_count=contradicted,
            total_claims=total,
            source_passage=source_passage,
            model_answer=model_answer,
        )
