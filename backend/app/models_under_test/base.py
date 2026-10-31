"""
base.py — ModelAdapter abstract base class.

Any model under test must implement this interface.
This allows plugging in a real fine-tuned Tamil LLM (HuggingFace, vLLM,
or local) alongside the current Groq-hosted general models, without
changing any evaluation pipeline code.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class ModelMetadata:
    """
    Honest description of the model.  The UI displays this verbatim.
    Never invent a specialisation that does not exist.
    """
    model_id: str                          # exact identifier used in API calls
    provider: str                          # e.g. "groq", "huggingface", "vllm", "local"
    display_name: str                      # human-readable name for the UI
    description: str                       # honest description of what it is
    is_fine_tuned_for_tamil_law: bool      # True ONLY if actually fine-tuned
    fine_tuning_dataset: Optional[str]     # name/URL of fine-tuning dataset, if applicable
    base_model: Optional[str]              # underlying base model, if applicable
    parameter_count: Optional[str]         # e.g. "8B", "70B"
    context_window: Optional[int]          # max tokens


@dataclass
class ModelResponse:
    raw_text: str                  # verbatim, unedited response from the model
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    http_status: int
    retry_count: int
    error: Optional[str] = None    # non-None means the call failed


class ModelAdapter(ABC):
    """
    Abstract adapter for a model under test.

    Subclasses implement `complete` and `metadata`.
    The pipeline calls `complete` for every benchmark item and stores
    the raw ModelResponse without modification.
    """

    @property
    @abstractmethod
    def metadata(self) -> ModelMetadata:
        """Return honest, accurate metadata about this model."""
        ...

    @abstractmethod
    def complete(
        self,
        system_prompt: Optional[str],
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 512,
        seed: Optional[int] = None,
        run_id: Optional[str] = None,
    ) -> ModelResponse:
        """
        Send one prompt and return the raw response.

        The implementation must:
        - Never edit or clean the raw response text.
        - Record retries and return retry_count.
        - If the call fails irrecoverably, return ModelResponse with
          raw_text="" and a non-None error string (never raise to the
          pipeline caller).
        """
        ...

    def is_available(self) -> bool:
        """
        Return True if the model can currently accept requests.
        Default implementation tries a minimal test call.
        Subclasses may override with a cheaper check.
        """
        try:
            resp = self.complete(None, "ping", max_tokens=1)
            return resp.error is None
        except Exception:
            return False
