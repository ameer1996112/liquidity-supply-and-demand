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
    paper_account_balance: float = 50000.0
    account_balance: float = 50000.0
    risk_percent: float = 0.5  # Aligned with Pine Balanced profile
    min_rr_ratio: float = 0.0  # Disabled: Pine Script handles SL/TP rules. Set > 0 to enable backend R:R filter.
    stop_loss_buffer_pips: float = Field(default=1.0, ge=0.0, le=5.0, description="Extra pips added to SL beyond zone boundary (Pine: 1.0)")
    max_lot_size: float = Field(default=10.0, ge=0.1, le=100.0, description="Maximum position size in lots (Pine: 10.0)")
    gold_pip_divisor: float = 0.1

    ai_filter_enabled: bool = Field(default=True, description="Enable AI Guardian validation layer.")
    ai_provider: Literal["openai", "anthropic"] = Field(default="anthropic", description="AI provider.")
    ai_api_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices("AI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"),
    )
    ai_base_url: str = Field(default="", description="AI API base URL (empty uses provider default).")
    ai_min_confidence: int = Field(default=75, ge=0, le=100, description="Minimum AI confidence (0-100).")
    ai_timeout_seconds: float = Field(default=5.0, gt=0, le=30, description="AI API timeout (seconds).")
    ai_model: str = Field(default="llama-3.3-70b-versatile", description="AI model name.")

    ml_guardian_enabled: bool = Field(default=True, description="Enable ML Guardian.")
    ml_min_confidence: float = Field(default=0.60, ge=0.0, le=1.0, description="Minimum ML win probability (0-1).")
    ml_use_adaptive_threshold: bool = Field(
        default=True,
        description="Use model win-rate aware adaptive RF threshold.",
    )
    ml_adaptive_threshold_floor: float = Field(
        default=0.30,
        ge=0.0,
        le=1.0,
        description="Minimum RF threshold floor after adaptive tuning.",
    )
    ml_adaptive_threshold_margin: float = Field(
        default=0.08,
        ge=0.0,
        le=1.0,
        description="Added margin over model base win-rate when adaptive threshold is enabled.",
    )
    ml_flip_threshold_offset: float = Field(
        default=-0.03,
        ge=-0.5,
        le=0.5,
        description="Threshold offset for FLIP entry model.",
    )
    ml_break_candle_threshold_offset: float = Field(
        default=0.00,
        ge=-0.5,
        le=0.5,
        description="Threshold offset for BREAK_CANDLE entry model.",
    )
    ml_dir_close_threshold_offset: float = Field(
        default=-0.01,
        ge=-0.5,
        le=0.5,
        description="Threshold offset for DIR_CLOSE entry model.",
    )

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
    llm_model_primary: str = Field(
        default="llama-3.3-70b-versatile",
        min_length=1,
        description="Primary LLM model id for ensemble decision calls.",
        validation_alias=AliasChoices("LLM_MODEL_PRIMARY", "LLM_MODEL"),
    )
    llm_model_fallback: str = Field(
        default="llama-3.1-8b-instant",
        description="Fallback LLM model id used when primary is unavailable (e.g., 404 model not found).",
        validation_alias=AliasChoices("LLM_MODEL_FALLBACK", "LLM_FALLBACK_MODEL"),
    )

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
    # Optional: JSON array of {name, account_id, token_env_key, risk_pct, max_positions, run_mode} for multi-account (Package A)
    broker_profiles_json: str = Field(default="", description="BROKER_PROFILES_JSON: optional list of broker profiles for one-signal-many-accounts")
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

    # ── Transaction Cost Analysis (TCA) Settings ─────────────────────────
    tca_enabled: bool = Field(default=True, description="Enable Transaction Cost Analysis tracking")
    tca_slippage_threshold_pips: float = Field(default=3.0, ge=0.0, description="Alert threshold for slippage (pips)")
    tca_latency_threshold_ms: int = Field(default=5000, ge=0, description="Alert threshold for execution latency (milliseconds)")
    tca_spread_threshold_pips: float = Field(default=5.0, ge=0.0, description="Warning threshold for wide spreads (pips)")

    # ── Portfolio Risk Management Settings ────────────────────────────────
    # Portfolio VaR (Value at Risk) limits
    portfolio_var_enabled: bool = Field(default=True, description="Enable portfolio VaR guard")
    portfolio_max_var_usd: float = Field(default=500.0, ge=0.0, description="Maximum portfolio VaR in USD")
    portfolio_max_var_pct: float = Field(default=5.0, ge=0.0, le=20.0, description="Maximum portfolio VaR as % of equity")

    # Sector exposure limits (as fraction of equity, 0.0-10.0 for leveraged products)
    sector_limit_forex_majors: float = Field(default=0.40, ge=0.0, le=10.0, description="Max exposure to forex majors (% of equity)")
    sector_limit_forex_jpy: float = Field(default=0.20, ge=0.0, le=10.0, description="Max exposure to JPY crosses (% of equity)")
    sector_limit_forex_eur: float = Field(default=0.30, ge=0.0, le=10.0, description="Max exposure to EUR crosses (% of equity)")
    sector_limit_forex_gbp: float = Field(default=0.30, ge=0.0, le=10.0, description="Max exposure to GBP crosses (% of equity)")
    sector_limit_indices_us: float = Field(default=0.30, ge=0.0, le=10.0, description="Max exposure to US indices (% of equity)")
    sector_limit_indices_eu: float = Field(default=0.20, ge=0.0, le=10.0, description="Max exposure to EU indices (% of equity)")
    sector_limit_indices_asia: float = Field(default=0.20, ge=0.0, le=10.0, description="Max exposure to Asian indices (% of equity)")
    sector_limit_precious_metals: float = Field(default=0.10, ge=0.0, le=10.0, description="Max exposure to precious metals (% of equity)")
    sector_limit_commodities: float = Field(default=0.15, ge=0.0, le=10.0, description="Max exposure to commodities (% of equity)")
    sector_limit_crypto: float = Field(default=0.10, ge=0.0, le=10.0, description="Max exposure to crypto (% of equity)")

    # Kelly Criterion position sizing
    kelly_enabled: bool = Field(default=False, description="Enable Kelly Criterion position sizing")
    kelly_fraction: float = Field(default=0.25, ge=0.01, le=1.0, description="Fractional Kelly multiplier (0.25 = quarter Kelly)")

    # Correlation matrix settings
    correlation_matrix_enabled: bool = Field(default=True, description="Enable real correlation matrix checks")
    max_avg_portfolio_correlation: float = Field(default=0.7, ge=0.0, le=1.0, description="Max average correlation with portfolio")

    # ── Multi-Account Background Sync Settings ────────────────────────────
    account_sync_enabled: bool = Field(default=False, description="Enable background account sync from MetaAPI")
    account_sync_interval_seconds: int = Field(default=60, ge=10, le=3600, description="Account sync interval in seconds (10-3600)")
    account_cache_ttl_seconds: int = Field(default=30, ge=5, le=300, description="Account data cache TTL in seconds (5-300)")

    # ── MTM Guardian Settings (Real-time Floating PnL Tracking) ───────────
    mtm_guardian_enabled: bool = Field(default=True, description="Enable MTM Guardian for real-time equity monitoring")
    mtm_cache_ttl_seconds: int = Field(default=10, ge=1, le=60, description="MTM cache refresh interval (seconds)")

    # ── Staleness Guard Settings (Webhook Latency Protection) ─────────────
    enable_staleness_guard: bool = Field(default=True, description="Enable staleness guard to reject delayed signals")
    staleness_max_age_seconds: int = Field(default=5, ge=1, le=30, description="Maximum signal age before rejection (seconds)")
    staleness_max_price_deviation_pips: float = Field(default=3.0, ge=0.5, le=10.0, description="Maximum price movement from signal entry (pips)")

    # ── Consistency Analyzer Settings (Prop Firm Compliance) ──────────────
    consistency_enabled: bool = Field(default=True, description="Enable consistency analyzer (FTMO 40% rule)")
    consistency_limit_pct: float = Field(default=40.0, ge=20.0, le=60.0, description="Max % of total profit from single day (FTMO: 40%)")


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
