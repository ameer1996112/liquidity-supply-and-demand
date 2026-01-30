"""
Centralized configuration using Pydantic BaseSettings.
Used by API (main.py) and Worker (worker.py).
Fail-fast: SUPABASE_URL, REDIS_URL must be set. WEBHOOK_SECRET optional (when set, API validates it).

AI Guardian Settings:
- AI_FILTER_ENABLED: Master toggle for AI validation layer
- AI_PROVIDER: "openai" or "anthropic"
- AI_API_KEY: Secret API key for the chosen provider
- AI_MIN_CONFIDENCE: Trades below this score (0-100) are dropped
- AI_TIMEOUT_SECONDS: Max wait time for AI response before allowing passthrough
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Load from environment (and .env file). Required: SUPABASE_URL, REDIS_URL. Optional: WEBHOOK_SECRET."""

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_nested_delimiter="__",
        populate_by_name=True,
    )

    # Required (fail fast if missing)
    supabase_url: str = Field(..., min_length=1, description="SUPABASE_URL")
    redis_url: str = Field(..., min_length=1, description="REDIS_URL")
    # Optional: when set, /webhook requests must send this secret (header X-Webhook-Secret or Authorization: Bearer <secret>)
    webhook_secret: str = Field(default="", description="WEBHOOK_SECRET")

    # Supabase key (SUPABASE_ANON_KEY or SUPABASE_KEY)
    supabase_key: str = Field(default="", validation_alias=AliasChoices("SUPABASE_ANON_KEY", "SUPABASE_KEY"))

    # Optional: used by worker/logic (not by API)
    discord_webhook_url: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    paper_trading_enabled: bool = False
    paper_auto_execute: bool = True
    paper_symbols: str = ""  # comma-separated, empty = all
    paper_max_positions: int = 10
    paper_account_balance: float = 10000.0
    account_balance: float = 10000.0
    risk_percent: float = 1.0
    min_rr_ratio: float = 1.0
    gold_pip_divisor: float = 0.1

    # ══════════════════════════════════════════════════════════
    # AI GUARDIAN SETTINGS
    # ══════════════════════════════════════════════════════════
    # Master toggle: Set to False to disable AI validation (passthrough mode)
    ai_filter_enabled: bool = Field(
        default=True,
        description="Enable AI Guardian validation layer. When False, all trades pass through without AI check."
    )

    # Provider selection: "openai" or "anthropic"
    ai_provider: Literal["openai", "anthropic"] = Field(
        default="anthropic",
        description="AI provider for trade validation. Options: 'openai' or 'anthropic'"
    )

    # API Key (loaded from AI_API_KEY or OPENAI_API_KEY or ANTHROPIC_API_KEY)
    ai_api_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices("AI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"),
        description="API key for the AI provider"
    )

    # Base URL for OpenAI-compatible APIs (Groq, OpenAI, etc.)
    ai_base_url: str = Field(
        default="https://api.groq.com/openai/v1",
        description="AI API base URL. Default: Groq. Use https://api.openai.com/v1 for OpenAI."
    )

    # Minimum confidence threshold (0-100). Trades below this are rejected.
    ai_min_confidence: int = Field(
        default=75,
        ge=0,
        le=100,
        description="Minimum AI confidence score (0-100) to approve a trade. Lower scores are rejected."
    )

    # Timeout for AI API calls (seconds). On timeout, trade is allowed (fail-open).
    ai_timeout_seconds: float = Field(
        default=5.0,
        gt=0,
        le=30,
        description="Timeout in seconds for AI API calls. On timeout/error, trade passes through (fail-open)."
    )

    # Model override (optional). Default: llama3-70b-8192 for Groq.
    ai_model: str = Field(
        default="llama3-70b-8192",
        description="AI model to use. Default: llama3-70b-8192 (Groq). Empty = use provider default."
    )


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
