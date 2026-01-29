"""
Centralized configuration using Pydantic BaseSettings.
Used by API (main.py) and Worker (worker.py).
Fail-fast: SUPABASE_URL, REDIS_URL, WEBHOOK_SECRET must be set (API needs all three for zero-drop).
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Load from environment (and .env file). Required: SUPABASE_URL, REDIS_URL, WEBHOOK_SECRET."""

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_nested_delimiter="__",
        populate_by_name=True,
    )

    # Required for API (fail fast if missing)
    supabase_url: str = Field(..., min_length=1, description="SUPABASE_URL")
    redis_url: str = Field(..., min_length=1, description="REDIS_URL")
    webhook_secret: str = Field(..., min_length=1, description="WEBHOOK_SECRET")

    # Supabase key (SUPABASE_ANON_KEY or SUPABASE_KEY)
    supabase_key: str = Field(default="", validation_alias=["SUPABASE_ANON_KEY", "SUPABASE_KEY"])

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


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
