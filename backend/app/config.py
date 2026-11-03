"""
config.py — Application configuration loaded from environment variables.

All settings are validated at startup.  If GROQ_API_KEY is absent or empty,
llm_enabled is set to False and all LLM-dependent features are disabled
with a visible message; the app still starts.

No secrets are ever logged or exposed through the API.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── LLM / Groq ────────────────────────────────────────────────────────────
    # Primary key — required for LLM features
    groq_api_key: Optional[str] = Field(default=None, alias="GROQ_API_KEY")
    # Optional fallback keys (comma-separated) rotated on 429 rate-limit errors
    groq_api_key_fallbacks: Optional[str] = Field(default=None, alias="GROQ_API_KEY_FALLBACKS")
    groq_model_under_test: str = Field(
        default="qwen/qwen3.8-27b", alias="GROQ_MODEL_UNDER_TEST"
    )
    groq_model_judge: str = Field(
        default="openai/gpt-oss-120b", alias="GROQ_MODEL_JUDGE"
    )
    groq_model_nli: str = Field(
        default="qwen/qwen3.8-27b", alias="GROQ_MODEL_NLI"
    )
    groq_requests_per_minute: int = Field(
        default=30, ge=1, le=600, alias="GROQ_REQUESTS_PER_MINUTE"
    )

    # ── Database ───────────────────────────────────────────────────────────────
    database_url: str = Field(
        default="sqlite:///./data/app.db", alias="DATABASE_URL"
    )

    # ── Calibration thresholds ────────────────────────────────────────────────
    kappa_threshold: float = Field(
        default=0.6, ge=0.0, le=1.0, alias="KAPPA_THRESHOLD"
    )
    min_labeled_items_for_calibration: int = Field(
        default=30, ge=1, alias="MIN_LABELED_ITEMS_FOR_CALIBRATION"
    )

    # ── Bootstrap ─────────────────────────────────────────────────────────────
    bootstrap_resamples: int = Field(
        default=2000, ge=100, alias="BOOTSTRAP_RESAMPLES"
    )
    bootstrap_seed: int = Field(default=42, alias="BOOTSTRAP_SEED")

    # ── Fetcher ───────────────────────────────────────────────────────────────
    fetcher_user_agent: str = Field(
        default="TamilNyaya-Bench/0.1 (research project)",
        alias="FETCHER_USER_AGENT",
    )
    fetcher_timeout_seconds: int = Field(
        default=30, ge=5, alias="FETCHER_TIMEOUT_SECONDS"
    )
    data_raw_dir: Path = Field(
        default=Path("./data/raw"), alias="DATA_RAW_DIR"
    )

    # ── Derived (not from env) ────────────────────────────────────────────────
    llm_enabled: bool = False          # set by model_validator below
    llm_disabled_reason: str = ""
    all_groq_keys: list[str] = Field(default_factory=list)  # populated by validator

    @model_validator(mode="after")
    def _check_llm(self) -> "Settings":
        key = self.groq_api_key
        placeholder = "your_groq_api_key_here"

        # Collect all valid keys: primary + fallbacks
        all_keys: list[str] = []
        if key and key.strip() and key.strip() != placeholder:
            all_keys.append(key.strip())
        if self.groq_api_key_fallbacks:
            for k in self.groq_api_key_fallbacks.split(","):
                k = k.strip()
                if k and k != placeholder:
                    all_keys.append(k)

        if not all_keys:
            self.llm_enabled = False
            self.llm_disabled_reason = (
                "GROQ_API_KEY is missing or not set. "
                "Add it to .env to enable LLM features."
            )
        else:
            self.llm_enabled = True
            self.all_groq_keys = all_keys
        return self

    @field_validator("data_raw_dir", mode="before")
    @classmethod
    def _ensure_raw_dir(cls, v: str | Path) -> Path:
        p = Path(v)
        p.mkdir(parents=True, exist_ok=True)
        return p

    def safe_dict(self) -> dict:
        """Return settings as a dict with API keys redacted and types JSON-safe."""
        d = self.model_dump(mode="json")
        if d.get("groq_api_key"):
            d["groq_api_key"] = "***REDACTED***"
        if d.get("groq_api_key_fallbacks"):
            d["groq_api_key_fallbacks"] = "***REDACTED***"
        d["all_groq_keys"] = f"[{len(self.all_groq_keys)} key(s) configured]"
        return d


# Module-level singleton — import this everywhere
settings = Settings()
