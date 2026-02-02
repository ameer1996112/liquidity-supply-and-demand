"""
Centralized configuration using Pydantic BaseSettings.
Used by API and Worker. Fail-fast: SUPABASE_URL, REDIS_URL must be set.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# .env at project root (parent of config/)
_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Load from environment (and .env file). Required: SUPABASE_URL, REDIS_URL. Optional: WEBHOOK_SECRET."""

    model_config = SettingsConfigDict(
        env_file=_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_nested_delimiter="__",
        populate_by_name=True,
    )

    supabase_url: str = Field(..., min_length=1, description="SUPABASE_URL")
    redis_url: str = Field(..., min_length=1, description="REDIS_URL")
    webhook_secret: str = Field(default="", description="WEBHOOK_SECRET")
    supabase_key: str = Field(default="", validation_alias=AliasChoices("SUPABASE_ANON_KEY", "SUPABASE_KEY"))
    supabase_service_role_key: str = Field(default="", validation_alias=AliasChoices("SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_SERVICE_KEY"))

    discord_webhook_url: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    paper_trading_enabled: bool = False
    paper_auto_execute: bool = True

    trading_kill_switch: bool = Field(
        default=False,
        description="Kill-switch: when True, block all execution.",
        validation_alias=AliasChoices("TRADING_KILL_SWITCH", "KILL_SWITCH"),
    )
    live_trading_enabled: bool = Field(
        default=False,
        description="Gate: False=DRY_RUN, True=allow orders.",
        validation_alias=AliasChoices("LIVE_TRADING", "LIVE_TRADING_ENABLED"),
    )
    run_mode: Literal["DRY_RUN", "PAPER", "LIVE"] = Field(
        default="DRY_RUN",
        description="Execution mode.",
        validation_alias=AliasChoices("RUN_MODE", "RUN_MODE"),
    )
    live_shadow: bool = Field(
        default=True,
        description="LIVE shadow mode: log only, no broker API calls.",
        validation_alias=AliasChoices("LIVE_SHADOW", "LIVE_SHADOW"),
    )
    paper_symbols: str = ""
    paper_max_positions: int = 10
    paper_account_balance: float = 10000.0
    account_balance: float = 10000.0
    risk_percent: float = 1.0
    min_rr_ratio: float = 1.0
    gold_pip_divisor: float = 0.1

    ai_filter_enabled: bool = Field(default=True, description="Enable AI Guardian validation layer.")
    ai_provider: Literal["openai", "anthropic"] = Field(default="anthropic", description="AI provider.")
    ai_api_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices("AI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"),
    )
    ai_base_url: str = Field(default="https://api.groq.com/openai/v1", description="AI API base URL.")
    ai_min_confidence: int = Field(default=75, ge=0, le=100, description="Minimum AI confidence (0-100).")
    ai_timeout_seconds: float = Field(default=5.0, gt=0, le=30, description="AI API timeout (seconds).")
    ai_model: str = Field(default="llama-3.3-70b-versatile", description="AI model name.")

    ml_guardian_enabled: bool = Field(default=True, description="Enable ML Guardian.")
    ml_min_confidence: float = Field(default=0.60, ge=0.0, le=1.0, description="Minimum ML win probability (0-1).")

    trinity_enabled: bool = Field(default=True, description="Enable Trinity Engine.")
    trinity_max_daily_loss_pct: float = Field(default=4.0, ge=0.1, le=10.0)
    trinity_max_drawdown_pct: float = Field(default=8.0, ge=1.0, le=20.0)
    trinity_max_risk_per_trade_pct: float = Field(default=1.0, ge=0.1, le=5.0)
    trinity_max_positions: int = Field(default=3, ge=1, le=10)
    trinity_max_currency_exposure: int = Field(default=2, ge=1, le=5)
    trinity_max_correlation_group: int = Field(default=1, ge=1, le=3)
    trinity_allow_hedging: bool = Field(default=False)

    usdjpy_rate: float = Field(default=150.0, ge=50.0, le=300.0)
    us30_point_value: float = Field(default=1.0, ge=0.1, le=100.0)
    nas100_point_value: float = Field(default=1.0, ge=0.1, le=100.0)


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
