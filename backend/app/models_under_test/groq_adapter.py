"""
groq_adapter.py — ModelAdapter implementation for Groq-hosted models.

These are GENERAL-PURPOSE open models hosted on Groq's inference API.
They are NOT fine-tuned for Tamil law.  The metadata.description field
makes this explicit in every UI display.
"""

from __future__ import annotations

from typing import Optional

from ..config import settings
from ..llm.groq_client import chat_completion, LLMDisabledError, LLMResponseError
from .base import ModelAdapter, ModelMetadata, ModelResponse


class GroqAdapter(ModelAdapter):
    """
    Adapter for any model available on the Groq API
    (https://api.groq.com/openai/v1).

    The model is identified by its exact Groq model ID (e.g. llama-3.1-8b-instant).
    """

    def __init__(self, model_id: Optional[str] = None) -> None:
        self._model_id = model_id or settings.groq_model_under_test

    @property
    def metadata(self) -> ModelMetadata:
        return ModelMetadata(
            model_id=self._model_id,
            provider="groq",
            display_name=f"{self._model_id} (Groq)",
            description=(
                f"{self._model_id} — general-purpose open model hosted on Groq's "
                "inference API. NOT fine-tuned for Tamil law or Indian legal text. "
                "Evaluated here as a baseline to measure hallucination in a "
                "general model on Tamil legal questions."
            ),
            is_fine_tuned_for_tamil_law=False,
            fine_tuning_dataset=None,
            base_model=None,       # Groq does not expose this in the API
            parameter_count=None,  # Groq does not expose this in the API
            context_window=None,   # Groq does not expose this in the API
        )

    def complete(
        self,
        system_prompt: Optional[str],
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 512,
        seed: Optional[int] = None,
        run_id: Optional[str] = None,
    ) -> ModelResponse:
        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})

        try:
            resp = chat_completion(
                messages=messages,
                model=self._model_id,
                temperature=temperature,
                max_tokens=max_tokens,
                seed=seed,
                run_id=run_id,
            )
            return ModelResponse(
                raw_text=resp.content,
                prompt_tokens=resp.prompt_tokens,
                completion_tokens=resp.completion_tokens,
                latency_ms=resp.latency_ms,
                http_status=resp.http_status,
                retry_count=resp.retry_count,
            )

        except LLMDisabledError as exc:
            return ModelResponse(
                raw_text="",
                prompt_tokens=0,
                completion_tokens=0,
                latency_ms=0,
                http_status=0,
                retry_count=0,
                error=f"LLM disabled: {exc}",
            )

        except LLMResponseError as exc:
            return ModelResponse(
                raw_text="",
                prompt_tokens=0,
                completion_tokens=0,
                latency_ms=0,
                http_status=0,
                retry_count=0,
                error=str(exc),
            )

        except Exception as exc:
            return ModelResponse(
                raw_text="",
                prompt_tokens=0,
                completion_tokens=0,
                latency_ms=0,
                http_status=0,
                retry_count=0,
                error=f"Unexpected: {exc}",
            )
