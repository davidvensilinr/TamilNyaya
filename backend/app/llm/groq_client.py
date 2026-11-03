"""
groq_client.py — Throttled, retrying Groq API client with key rotation.

Rules:
- Maintains one token-bucket per API key so each key gets its own quota.
- On HTTP 429 (rate limit), immediately rotates to the next available key
  instead of sleeping and retrying on the same key.
- Exponential back-off only applies when ALL keys are exhausted.
- Every retry / rotation is logged to the audit log.
- The API key is NEVER printed, logged or returned to the frontend.
- If LLM is disabled (no key), raises LLMDisabledError immediately.
- Responses are cached by (model, prompt hash) only when the caller
  explicitly passes cache=True.
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


# ── Per-key token-bucket rate limiter ─────────────────────────────────────────


class _TokenBucket:
    def __init__(self, rate_per_minute: int) -> None:
        self._rate = rate_per_minute
        self._tokens: float = float(rate_per_minute)
        self._last_refill: float = time.monotonic()
        self.rate_limited_until: float = 0.0  # epoch seconds; set on 429

    def acquire(self) -> float:
        """Return seconds to sleep before this key is ready."""
        # If this key is in a 429 cooldown, report how long left
        now_wall = time.time()
        if self.rate_limited_until > now_wall:
            return self.rate_limited_until - now_wall

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

    def mark_rate_limited(self, cooldown_seconds: float = 60.0) -> None:
        """Mark this key as rate-limited for the given duration."""
        self.rate_limited_until = time.time() + cooldown_seconds


# ── Key pool — one bucket per API key ────────────────────────────────────────

class _KeyPool:
    """Round-robin pool of Groq API keys, each with its own rate limiter."""

    def __init__(self) -> None:
        self._keys: list[str] = []
        self._buckets: list[_TokenBucket] = []
        self._index: int = 0

    def _init(self) -> None:
        """Lazily initialise from settings (so tests can monkeypatch settings)."""
        if not self._keys:
            self._keys = list(settings.all_groq_keys)
            self._buckets = [
                _TokenBucket(settings.groq_requests_per_minute)
                for _ in self._keys
            ]

    def next_available(self) -> tuple[str, _TokenBucket, int]:
        """Return (api_key, bucket, key_index) for the next available key.

        Prefers a key whose bucket has tokens ready.  If all keys are busy,
        returns the one with the shortest wait.
        """
        self._init()
        best_key_idx = self._index % len(self._keys)
        best_wait = float("inf")

        for offset in range(len(self._keys)):
            idx = (self._index + offset) % len(self._keys)
            wait = self._buckets[idx].acquire.__self__._TokenBucket__tokens  # peek
            # Use acquire() to get actual wait time — it also updates tokens
            wait = self._buckets[idx].acquire()
            if wait == 0.0:
                self._index = (idx + 1) % len(self._keys)
                return self._keys[idx], self._buckets[idx], idx
            if wait < best_wait:
                best_wait = wait
                best_key_idx = idx

        self._index = (best_key_idx + 1) % len(self._keys)
        return self._keys[best_key_idx], self._buckets[best_key_idx], best_key_idx

    def rotate_after_rate_limit(self, key_idx: int, cooldown: float = 62.0) -> None:
        """Mark a specific key as rate-limited and advance the pool index."""
        self._init()
        self._buckets[key_idx].mark_rate_limited(cooldown)
        self._index = (key_idx + 1) % len(self._keys)

    @property
    def key_count(self) -> int:
        self._init()
        return len(self._keys)


_pool = _KeyPool()


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

MAX_RETRIES = 8   # across all keys combined


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
    Send a chat completion request to Groq, rotating through available API keys
    on 429 rate-limit errors instead of sleeping on the same key.

    Raises
    ------
    LLMDisabledError   : No key configured.
    LLMRateLimitError  : All keys rate-limited after MAX_RETRIES.
    LLMResponseError   : Non-recoverable API error.
    """
    from .. import audit  # lazy import to avoid circular dependency

    if not settings.llm_enabled:
        raise LLMDisabledError(settings.llm_disabled_reason)

    _model = model or settings.groq_model_under_test

    if cache:
        ck = _cache_key(_model, messages, temperature=temperature, max_tokens=max_tokens)
        if ck in _response_cache:
            cached = _response_cache[ck]
            cached.cached = True
            return cached

    try:
        from groq import Groq, RateLimitError, APIStatusError
    except ImportError as exc:
        raise LLMDisabledError("groq package not installed") from exc

    kwargs: dict = {
        "model": _model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if seed is not None:
        kwargs["seed"] = seed

    retry_count = 0
    last_exc: Optional[Exception] = None

    for attempt in range(MAX_RETRIES):
        api_key, bucket, key_idx = _pool.next_available()
        wait = bucket.acquire()
        if wait > 0:
            time.sleep(min(wait, 5.0))  # cap single sleep at 5s; rotate will help more

        client = Groq(api_key=api_key)
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
                _response_cache[ck] = result  # type: ignore[possibly-undefined]
            return result

        except RateLimitError as exc:
            last_exc = exc
            retry_count += 1
            # Mark this key as rate-limited and rotate immediately
            _pool.rotate_after_rate_limit(key_idx, cooldown=62.0)
            audit.log_retry(
                "llm_rate_limit",
                f"Key #{key_idx + 1} rate-limited on attempt {attempt + 1}; "
                f"rotating to next key ({_pool.key_count} keys available)",
                run_id=run_id,
            )
            # Only sleep if we've exhausted all keys in this round
            if retry_count % _pool.key_count == 0:
                backoff = 5.0 + random.uniform(0.0, 2.0)
                audit.log_retry(
                    "llm_all_keys_limited",
                    f"All {_pool.key_count} key(s) rate-limited; sleeping {backoff:.1f}s",
                    run_id=run_id,
                )
                time.sleep(backoff)

        except APIStatusError as exc:
            if exc.status_code >= 500:
                last_exc = exc
                retry_count += 1
                backoff = (2 ** min(attempt, 4)) + random.uniform(0.0, 1.0)
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
        f"Rate limit not resolved after {MAX_RETRIES} retries across {_pool.key_count} key(s). "
        f"Last error: {last_exc}"
    )


def verify_model_availability(model_name: str) -> tuple[bool, list[str]]:
    """
    Check whether model_name is in Groq's live model list.
    Uses the primary API key. Fails gracefully if the API is unreachable.
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
