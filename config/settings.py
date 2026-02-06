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

    # Dynamic risk scaling (swarm-inspired)
    enable_risk_scaling: bool = True
    drawdown_threshold_1: float = 0.02  # -2% daily loss
    risk_reduction_1: float = 0.5       # 50% size
    drawdown_threshold_2: float = 0.03  # -3% daily loss
    risk_reduction_2: float = 0.25      # 25% size

    # Asymmetric compounding / Step-Up Protocol
    risk_mode: str = "step_up"  # "linear" or "step_up"
    volatility_targeting: bool = True
    step_up_threshold_1: float = 0.02  # +2% profit buffer
    step_up_risk_1: float = 1.0       # 1.0% risk in buffer
    step_up_threshold_2: float = 0.05  # +5% profit - kill zone
    step_up_risk_2: float = 2.0       # 2.0% risk when far ahead
    survival_risk: float = 0.5        # 0.5% when below starting equity

    # Ensemble brain / LLM filter
    enable_llm_filter: bool = True

    # Pine-matching deterministic pre-filters (mirror SND_Strategy.pine Balanced profile)
    pine_min_score: float = Field(default=60.0, ge=0.0, le=100.0, description="Min zone score (Pine ai_quality_threshold). 60=Balanced, 70=Conservative.")
    pine_min_grade: str = Field(default="C+", description="Min zone grade. A+/A/B+/B/C+/C. C+=Balanced, B+=Conservative.")
    pine_min_return_strength: float = Field(default=30.0, ge=0.0, le=100.0, description="Min return strength. 30=Balanced, 50=Conservative, 0=OFF.")
    pine_require_liq_swept: bool = Field(default=True, description="Require liquidity swept before entry (core S&D rule).")
    pine_min_departure_strength: float = Field(default=40.0, ge=0.0, le=100.0, description="Min departure strength (arrival rule). <40=compressed=reject.")
    pine_block_dead_zone: bool = Field(default=True, description="Block entries in last 10 min of each hour (xx:50-xx:00).")
    pine_trading_start_hour: int = Field(default=7, ge=0, le=23, description="Trading start hour (UTC). 7=default.")
    pine_trading_end_hour: int = Field(default=22, ge=0, le=23, description="Trading end hour (UTC). 22=default.")
    pine_max_trades_per_day: int = Field(default=2, ge=0, le=10, description="Max trades per day. 2=Balanced, 1=Conservative. 0=OFF.")

    # Shadow launch toggle for EnsembleBrain gating in worker
    run_shadow_mode: bool = False

    # External execution via MetaApi (MT5 over HTTP)
    meta_api_token: str = ""
    meta_api_account_id: str = ""
    meta_api_region: str = Field(
        default="new-york",
        description="MetaApi region slug (e.g. 'new-york', 'london', 'tokyo').",
        validation_alias="META_API_REGION",
    )
    execution_mode: str = "SHADOW"  # SHADOW | METAAPI (or others in future)

    usdjpy_rate: float = Field(default=150.0, ge=50.0, le=300.0)
    us30_point_value: float = Field(default=1.0, ge=0.1, le=100.0)
    nas100_point_value: float = Field(default=1.0, ge=0.1, le=100.0)

    # ── Evaluation Mode (Prop Firm Challenge Tracking) ──────────────────────
    evaluation_mode: bool = Field(default=False, description="Enable prop firm evaluation tracking")
    evaluation_phase: Literal["phase1", "phase2", "funded"] = Field(default="phase1", description="Current evaluation phase")
    evaluation_start_date: str = Field(default="", description="ISO datetime when evaluation started (YYYY-MM-DD)")

    # Phase 1 Rules (FTMO/MyFundedFX style)
    phase1_profit_target: float = Field(default=5000.0, ge=0.0, description="Phase 1 profit target ($)")
    phase1_max_daily_loss: float = Field(default=500.0, ge=0.0, description="Phase 1 max daily loss ($)")
    phase1_max_drawdown_pct: float = Field(default=5.0, ge=0.0, le=100.0, description="Phase 1 max drawdown (%)")
    phase1_min_trading_days: int = Field(default=4, ge=0, description="Phase 1 minimum trading days")

    # Phase 2 Rules
    phase2_profit_target: float = Field(default=2500.0, ge=0.0, description="Phase 2 profit target ($)")
    phase2_max_daily_loss: float = Field(default=500.0, ge=0.0, description="Phase 2 max daily loss ($)")
    phase2_max_drawdown_pct: float = Field(default=5.0, ge=0.0, le=100.0, description="Phase 2 max drawdown (%)")
    phase2_min_trading_days: int = Field(default=4, ge=0, description="Phase 2 minimum trading days")

    # Funded Account Rules
    funded_max_daily_loss: float = Field(default=500.0, ge=0.0, description="Funded account max daily loss ($)")
    funded_max_drawdown_pct: float = Field(default=10.0, ge=0.0, le=100.0, description="Funded account trailing drawdown (%)")

    # Consistency Rule
    consistency_target_pct: float = Field(default=70.0, ge=0.0, le=100.0, description="Consistency target (% of profitable days)")


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
