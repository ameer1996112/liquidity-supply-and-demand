"""
Centralized configuration using Pydantic BaseSettings.
Used by API (main.py) and Worker (worker.py).
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Load from environment (and .env file)."""

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_nested_delimiter="__",
        populate_by_name=True,
    )

    # Supabase (SUPABASE_URL, SUPABASE_KEY or SUPABASE_ANON_KEY)
    supabase_url: str = ""
    supabase_key: str = Field(default="", validation_alias=["SUPABASE_ANON_KEY", "SUPABASE_KEY"])

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Webhook security
    webhook_secret: str = ""

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
