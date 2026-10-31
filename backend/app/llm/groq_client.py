"""
groq_client.py — Throttled, retrying Groq API client.

Rules:
- Respects GROQ_REQUESTS_PER_MINUTE with a token-bucket throttle.
- Exponential back-off with jitter on HTTP 429 and 5xx.
- Every retry is logged to the audit log.
- The API key is NEVER printed, logged or returned to the frontend.
- If LLM is disabled (no key), raises LLMDisabledError immediately.
- Responses are cached by (model, prompt hash) only when the caller
  explicitly passes cache=True; cached responses are labelled with
  the original run timestamp.
"""

from __future__ import annotations

import hashlib
import json
import random
import time
from dataclasses import dataclass, field
from typing import Optional

from ..config import settings

# ── Errors ────────────────────────────────────────────────────────────────────


class LLMDisabledError(RuntimeError):
    """Raised when LLM features are disabled (no API key configured)."""


class LLMRateLimitError(RuntimeError):
    pass


class LLMResponseError(RuntimeError):
    pass


# ── Simple token-bucket rate limiter ─────────────────────────────────────────


class _TokenBucket:
    def __init__(self, rate_per_minute: int) -> None:
        self._rate = rate_per_minute
        self._tokens: float = float(rate_per_minute)
        self._last_refill: float = time.monotonic()

    def acquire(self) -> float:
        """Return the number of seconds to sleep before the next request."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._last_refill = now
        self._tokens = min(self._rate, self._tokens + elapsed * (self._rate / 60.0))
        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return 0.0
        wait = (1.0 - self._tokens) / (self._rate / 60.0)
        self._tokens = 0.0
        return wait


_bucket = _TokenBucket(settings.groq_requests_per_minute)


# ── Response dataclass ────────────────────────────────────────────────────────


@dataclass
class LLMResponse:
    model: str
    content: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    http_status: int
    retry_count: int
    cached: bool = False
    cached_from_run: Optional[str] = None
    raw: dict = field(default_factory=dict)


# ── Simple in-memory cache (keyed by model + SHA-256 of prompt) ──────────────
_response_cache: dict[str, LLMResponse] = {}


def _cache_key(model: str, messages: list[dict], **kwargs) -> str:
    payload = json.dumps({"model": model, "messages": messages, **kwargs}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


# ── Core chat completion ──────────────────────────────────────────────────────

MAX_RETRIES = 5


def chat_completion(
    messages: list[dict],
    model: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = 512,
    seed: Optional[int] = None,
    cache: bool = False,
    run_id: Optional[str] = None,
) -> LLMResponse:
    """
    Send a chat completion request to Groq.

    Parameters
    ----------
    messages  : OpenAI-format message list.
    model     : Model name (defaults to GROQ_MODEL_UNDER_TEST).
    temperature, max_tokens, seed : Generation parameters.
    cache     : If True, cache the response and label cache hits.
    run_id    : Audit-log association.

    Raises
    ------
    LLMDisabledError   : Key not configured.
    LLMRateLimitError  : Rate limit not resolved after MAX_RETRIES.
    LLMResponseError   : Non-recoverable API error.
    """
    from .. import audit  # lazy import to avoid circular dependency

    if not settings.llm_enabled:
        raise LLMDisabledError(settings.llm_disabled_reason)

    _model = model or settings.groq_model_under_test

    if cache:
        key = _cache_key(_model, messages, temperature=temperature, max_tokens=max_tokens)
        if key in _response_cache:
            cached = _response_cache[key]
            cached.cached = True
            return cached

    # Lazy-import groq so the app starts even if groq is not installed
    try:
        from groq import Groq, RateLimitError, APIStatusError
    except ImportError as exc:
        raise LLMDisabledError("groq package not installed") from exc

    client = Groq(api_key=settings.groq_api_key)

    kwargs: dict = {"model": _model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
    if seed is not None:
        kwargs["seed"] = seed

    retry_count = 0
    last_exc: Optional[Exception] = None

    for attempt in range(MAX_RETRIES):
        wait = _bucket.acquire()
        if wait > 0:
            time.sleep(wait)

        t_start = time.monotonic()
        try:
            response = client.chat.completions.create(**kwargs)
            latency_ms = int((time.monotonic() - t_start) * 1000)
            result = LLMResponse(
                model=_model,
                content=response.choices[0].message.content or "",
                prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
                completion_tokens=response.usage.completion_tokens if response.usage else 0,
                latency_ms=latency_ms,
                http_status=200,
                retry_count=retry_count,
                raw=response.model_dump() if hasattr(response, "model_dump") else {},
            )
            if cache:
                _response_cache[key] = result  # type: ignore[possibly-undefined]
            return result

        except RateLimitError as exc:
            last_exc = exc
            retry_count += 1
            backoff = (2 ** attempt) + random.uniform(0.0, 1.0)
            audit.log_retry(
                "llm_rate_limit",
                f"Rate limit on attempt {attempt + 1}; sleeping {backoff:.1f}s",
                run_id=run_id,
            )
            time.sleep(backoff)

        except APIStatusError as exc:
            if exc.status_code >= 500:
                last_exc = exc
                retry_count += 1
                backoff = (2 ** attempt) + random.uniform(0.0, 1.0)
                audit.log_retry(
                    "llm_server_error",
                    f"HTTP {exc.status_code} on attempt {attempt + 1}; sleeping {backoff:.1f}s",
                    run_id=run_id,
                )
                time.sleep(backoff)
            else:
                raise LLMResponseError(f"Groq API error {exc.status_code}: {exc.message}") from exc

        except Exception as exc:
            raise LLMResponseError(f"Unexpected error from Groq: {exc}") from exc

    raise LLMRateLimitError(
        f"Rate limit not resolved after {MAX_RETRIES} retries. Last error: {last_exc}"
    )


def verify_model_availability(model_name: str) -> tuple[bool, list[str]]:
    """
    Check whether model_name is in Groq's live model list.
    Returns (available: bool, available_models: list[str]).
    Fails gracefully if the API is unreachable.
    """
    if not settings.llm_enabled:
        return False, []
    try:
        from groq import Groq
        client = Groq(api_key=settings.groq_api_key)
        models = client.models.list()
        available = [m.id for m in models.data]
        return model_name in available, available
    except Exception:
        return False, []
