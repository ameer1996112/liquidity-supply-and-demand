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

    log_level: str = Field(
        default="INFO",
        description="Root log level: DEBUG | INFO | WARNING | ERROR. Env: LOG_LEVEL.",
        validation_alias=AliasChoices("LOG_LEVEL", "log_level"),
    )

    supabase_url: str = Field(..., min_length=1, description="SUPABASE_URL")
    redis_url: str = Field(..., min_length=1, description="REDIS_URL")
    webhook_secret: str = Field(default="", description="WEBHOOK_SECRET")
    admin_api_key: str = Field(default="", description="ADMIN_API_KEY — required to access operator/admin routes")
    public_api_base_url: str = Field(
        default="",
        description="Public base URL for the API (used for OAuth redirect URIs), e.g. https://your-api.up.railway.app",
        validation_alias=AliasChoices("PUBLIC_API_BASE_URL", "API_PUBLIC_BASE_URL"),
    )
    supabase_key: str = Field(default="", validation_alias=AliasChoices("SUPABASE_ANON_KEY", "SUPABASE_KEY"))
    supabase_service_role_key: str = Field(default="", validation_alias=AliasChoices("SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_SERVICE_KEY"))

    discord_webhook_url: str = ""
    discord_alerts_webhook_url: str = ""  # Optional: separate channel for operational alerts
    discord_bot_token: str = ""           # Optional: enables thread-per-trade (create threads from messages)
    discord_public_key: str = ""          # Required for slash command signature verification (from Discord Dev Portal)
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    jira_base_url: str = Field(default="https://ameer1996112.atlassian.net", validation_alias="JIRA_BASE_URL")
    jira_domain: str = Field(default="", validation_alias="JIRA_DOMAIN")
    jira_email: str = Field(default="", validation_alias="JIRA_EMAIL")
    jira_api_token: SecretStr = Field(default=SecretStr(""), validation_alias="JIRA_API_TOKEN")
    jira_project_key: str = Field(default="DEV", validation_alias="JIRA_PROJECT_KEY")
    jira_task_type_id: str = Field(default="10003", validation_alias="JIRA_TASK_TYPE_ID")
    paper_trading_enabled: bool = False
    paper_auto_execute: bool = True

    # cTrader Open API (Spotware) OAuth + Open API proxy auth
    ctrader_client_id: str = Field(default="", validation_alias=AliasChoices("CTRADER_CLIENT_ID", "CTRADER_OPENAPI_CLIENT_ID"))
    ctrader_client_secret: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices("CTRADER_CLIENT_SECRET", "CTRADER_OPENAPI_CLIENT_SECRET"),
    )
    ctrader_oauth_state_secret: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices("CTRADER_OAUTH_STATE_SECRET", "CTRADER_STATE_SECRET"),
        description="Optional: HMAC secret for cTrader OAuth state signing (fallbacks to WEBHOOK_SECRET).",
    )

    trading_kill_switch: bool = Field(
        default=False,
        description="Kill-switch: when True, block all execution.",
        validation_alias=AliasChoices("TRADING_KILL_SWITCH", "KILL_SWITCH"),
    )
    # DEPRECATED: live_trading_enabled ENV var has been removed.
    # Execution mode is now controlled exclusively via the dashboard
    # (system_config.trading_mode in DB). DRY_RUN | PAPER | LIVE.
    run_mode: Literal["DRY_RUN", "PAPER", "LIVE"] = Field(
        default="DRY_RUN",
        description="Fallback execution mode if system_config DB is unreachable. Authority is system_config.trading_mode.",
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
    risk_percent: float = 0.5  # Base risk % per trade (matches Pine risk_per_trade_pct=0.5). Step-up scales via PropGuard multiplier.
    min_rr_ratio: float = 0.0  # Disabled: Pine Script handles SL/TP rules. Set > 0 to enable backend R:R filter.
    stop_loss_buffer_pips: float = Field(default=1.0, ge=0.0, le=5.0, description="Extra pips added to SL beyond zone boundary (Pine: 1.0)")
    max_lot_size: float = Field(default=100.0, ge=0.1, le=1000.0, description="Maximum position size in lots (Pine: 100.0)")
    gold_pip_divisor: float = 0.1

    ai_filter_enabled: bool = Field(default=True, description="Enable AI Guardian validation layer.")
    # [optimization/ai-overhaul] Shadow Mode: AI runs and logs decisions but NEVER blocks trades.
    # Set AI_SHADOW_MODE=true to collect calibration data without losing any signals.
    ai_shadow_mode: bool = Field(default=False, description="AI Shadow Mode: log AI decisions but never block trades. Env: AI_SHADOW_MODE.")
    # [optimization/ai-overhaul] ML Warning Mode: RF confidence 10%-60% becomes WARNING, only <10% is hard REJECT.
    ml_warning_only_mode: bool = Field(default=True, description="RF gate: <10% = REJECT, 10-60% = WARNING (allow), >=60% = APPROVE. Env: ML_WARNING_ONLY_MODE.")
    ai_provider: Literal["anthropic", "openai", "gemini", "local"] = Field(
        default="anthropic",
        description="AI provider for unified client. anthropic|openai|gemini|local.",
        validation_alias=AliasChoices("AI_PROVIDER", "ai_provider"),
    )
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
    step_up_risk_2: float = 1.5       # 1.5% risk when far ahead (capped for prop firm safety)
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

    # ── Sprint 3.1: Two-tier LLM allocation ───────────────────────────────────
    ai_enabled: bool = Field(
        default=True,
        description="Enable AI/LLM layer. When False, LLM is skipped entirely.",
        validation_alias="AI_ENABLED",
    )
    ai_mode: Literal["shadow", "enforce"] = Field(
        default="shadow",
        description="shadow=log-only, never block; enforce=LLM NO_GO blocks execution.",
        validation_alias="AI_MODE",
    )
    ai_quick_model: str = Field(
        default="llama-3.1-8b-instant",
        description="Fast/cheap model for first-tier LLM call.",
        validation_alias="AI_QUICK_MODEL",
    )
    ai_deep_model: str = Field(
        default="llama-3.3-70b-versatile",
        description="Heavy model for escalation (second-tier) when rules trigger.",
        validation_alias="AI_DEEP_MODEL",
    )
    # Sprint 3.3: Debate guardrail (Bull vs Bear) — shadow mode only
    ai_debate_enabled: bool = Field(
        default=True,
        description="Run Bull/Bear/Risk/Chair debate and persist to ai_runs. Never blocks.",
        validation_alias="AI_DEBATE_ENABLED",
    )

    # ── Phase 1 Latency Optimization (2026-03-10) ────────────────────────────
    enable_fast_path_bypass: bool = Field(
        default=False,
        description="Skip full AI ensemble for high-confidence signals (latency optimization).",
        validation_alias="ENABLE_FAST_PATH_BYPASS",
    )
    fast_path_rf_threshold: float = Field(
        default=0.85,
        ge=0.5,
        le=1.0,
        description="Minimum RF confidence to trigger fast-path bypass (skip LLM).",
        validation_alias="FAST_PATH_RF_THRESHOLD",
    )
    fast_path_live_only: bool = Field(
        default=True,
        description="Only use fast-path in LIVE mode (full checks in PAPER for testing).",
        validation_alias="FAST_PATH_LIVE_ONLY",
    )
    async_notifications: bool = Field(
        default=False,
        description="Send Discord/Telegram notifications in background threads (non-blocking).",
        validation_alias="ASYNC_NOTIFICATIONS",
    )
    async_trading_council: bool = Field(
        default=False,
        description="Run Trading Council in background thread (shadow mode, non-blocking).",
        validation_alias="ASYNC_TRADING_COUNCIL",
    )
    enable_latency_instrumentation: bool = Field(
        default=False,
        description="Log detailed latency breakdowns per execution stage.",
        validation_alias="ENABLE_LATENCY_INSTRUMENTATION",
    )

    enable_multi_venue_streaming: bool = Field(
        default=False,
        description="Enable Binance/Bybit streaming bootstrap in worker loop. Env: ENABLE_MULTI_VENUE_STREAMING.",
        validation_alias=AliasChoices("ENABLE_MULTI_VENUE_STREAMING", "enable_multi_venue_streaming"),
    )
    tca_latency_threshold_ms: int = Field(
        default=30000,
        ge=100,
        le=60000,
        description="TCA alert threshold for high TOTAL execution latency (milliseconds). Set to 30s to account for broker delays on minor pairs.",
        validation_alias="TCA_LATENCY_THRESHOLD_MS",
    )
    tca_bot_latency_threshold_ms: int = Field(
        default=10000,
        ge=100,
        le=30000,
        description="Alert threshold for bot processing latency (signal→submit). Triggers if guard rails are slow.",
        validation_alias="TCA_BOT_LATENCY_THRESHOLD_MS",
    )
    tca_broker_latency_threshold_ms: int = Field(
        default=20000,
        ge=1000,
        le=60000,
        description="Alert threshold for broker execution latency (submit→fill). Triggers if broker/MetaAPI is slow.",
        validation_alias="TCA_BROKER_LATENCY_THRESHOLD_MS",
    )

    # Sprint 3.4: Strategy graduation — cannot enable enforce unless thresholds met
    ai_graduation_min_sample_size: int = Field(
        default=50,
        ge=10,
        le=500,
        description="Min closed trades in shadow before enabling enforce.",
        validation_alias="AI_GRADUATION_MIN_SAMPLE_SIZE",
    )
    ai_graduation_min_edge_pct: float = Field(
        default=5.0,
        ge=0.0,
        le=50.0,
        description="Min win-rate edge (allowed - blocked) % to enable enforce.",
        validation_alias="AI_GRADUATION_MIN_EDGE_PCT",
    )
    # Chart screenshots in notifications (default off -- enable after testing)
    chart_notifications_enabled: bool = Field(
        default=False,
        description="Generate candlestick chart screenshots and attach to Discord/Telegram notifications.",
        validation_alias="CHART_NOTIFICATIONS_ENABLED",
    )
    discord_signals_channel_id: str = Field(
        default="",
        description="Discord channel ID for signals (needed to edit messages with chart images).",
        validation_alias="DISCORD_SIGNALS_CHANNEL_ID",
    )

    # Sprint 4.3: Reflection + Memory loop (optional, default off)
    memory_enabled: bool = Field(
        default=False,
        description="Enable trade reflections and memory-augmented AI context. Creates post-mortem on close, retrieves similar past situations for new signals.",
        validation_alias="MEMORY_ENABLED",
    )
    memory_top_k: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Number of similar past reflections to feed into AI Guardian.",
        validation_alias="MEMORY_TOP_K",
    )

    # Pine-matching deterministic pre-filters (mirror SND_Strategy.pine Balanced profile)
    pine_min_score: float = Field(default=60.0, ge=0.0, le=100.0, description="Min zone score (Pine ai_quality_threshold). 60=Balanced, 70=Conservative.")
    pine_min_grade: str = Field(default="C+", description="Min zone grade. A+/A/B+/B/C+/C. C+=Balanced, B+=Conservative.")
    pine_min_return_strength: float = Field(default=30.0, ge=0.0, le=100.0, description="Min return strength. 30=Balanced, 50=Conservative, 0=OFF.")
    pine_require_liq_swept: bool = Field(default=True, description="Require liquidity swept before entry (core S&D rule).")
    pine_min_departure_strength: float = Field(default=40.0, ge=0.0, le=100.0, description="Min departure strength (arrival rule). <40=compressed=reject.")
    pine_block_dead_zone: bool = Field(default=True, description="[Deprecated: merged into HTF Candle Filter as 'Block Before Hourly Close'. DB key: pine_block_before_hourly_close] Legacy fallback for hourly close block.")
    pine_block_middle_zone: bool = Field(default=True, description="Block 1-candle liquidity trades where a better zone exists further in the trade direction. Pine only flags when the competing zone is active, has valid swept liquidity, is fresh (<24h), and unused.")
    pine_block_one_candle_liq: bool = Field(default=True, description="Block entries where liquidity was formed by a single candle, unless the setup meets high-confidence LSD criteria (no middle zone + trend aligned + swept + departure_strength>=60).")
    pine_one_candle_liq_min_departure: float = Field(default=60.0, ge=0.0, le=100.0, description="Min departure_strength required to allow a 1-candle liquidity setup when pine_block_one_candle_liq=True.")
    pine_htf_candle_filter_enabled: bool = Field(default=True, description="Block all entries 10 min before each 15-min HTF candle open (xx:05-14, xx:20-29, xx:35-44, xx:50-59). At candle opens (xx:00/15/30/45) only FLIP entries are allowed. Env: PINE_HTF_CANDLE_FILTER_ENABLED.")
    pine_htf_candle_block_minutes: int = Field(default=5, ge=1, le=14, description="How many minutes before each 15-min candle to block signals. Default: 5. Env: PINE_HTF_CANDLE_BLOCK_MINUTES.")
    pine_trading_start_hour: int = Field(default=6, ge=0, le=23, description="[Deprecated: use pine_trading_start_hour_local] Trading start hour (UTC). Kept for backward compat.")
    pine_trading_end_hour: int = Field(default=22, ge=0, le=23, description="[Deprecated: use pine_trading_end_hour_local] Trading end hour (UTC). Kept for backward compat.")
    pine_trading_timezone: str = Field(default="Asia/Jerusalem", description="Timezone for trading hour interpretation. Default: Asia/Jerusalem (Israel, auto-DST). Env: PINE_TRADING_TIMEZONE.")
    pine_trading_start_hour_local: int = Field(default=6, ge=0, le=23, description="Trading start hour in local timezone (pine_trading_timezone). 6=06:00 Israel. Env: PINE_TRADING_START_HOUR_LOCAL.")
    pine_trading_end_hour_local: int = Field(default=22, ge=0, le=23, description="Trading end hour in local timezone (pine_trading_timezone). 22=22:00 Israel. Env: PINE_TRADING_END_HOUR_LOCAL.")
    pine_max_trades_per_day: int = Field(default=0, ge=0, le=20, description="Legacy static daily trade cap (0=use adaptive system). Env: PINE_MAX_TRADES_PER_DAY.")

    # ── Adaptive Daily Trade Limit (v2 multi-dimensional) ─────────────────
    pine_adaptive_enabled: bool = Field(default=True, description="Enable session-quality adaptive trade limit. When False, uses pine_max_trades_per_day static cap. Env: PINE_ADAPTIVE_ENABLED.")
    pine_max_trades_london: int = Field(default=2, ge=0, le=10, description="Base trade slots for London session (07:00–12:00 UTC). Env: PINE_MAX_TRADES_LONDON.")
    pine_max_trades_ny: int = Field(default=2, ge=0, le=10, description="Base trade slots for New York session (13:00–18:00 UTC). Env: PINE_MAX_TRADES_NY.")
    pine_max_trades_offhours: int = Field(default=1, ge=0, le=10, description="Base trade slots for off-hours (18:00–07:00 UTC). Env: PINE_MAX_TRADES_OFFHOURS.")
    pine_max_trades_hard_cap: int = Field(default=6, ge=1, le=20, description="Absolute daily trade ceiling across all sessions. Env: PINE_MAX_TRADES_HARD_CAP.")
    pine_daily_risk_budget_pct: float = Field(default=3.0, ge=0.1, le=20.0, description="Max cumulative risk % that may be deployed per day (parallel budget gate). Env: PINE_DAILY_RISK_BUDGET_PCT.")
    pine_streak_enabled: bool = Field(default=True, description="Enable multi-day profitable-streak bonus (+1/+2 slots). Env: PINE_STREAK_ENABLED.")

    # Weekly loss limit
    enable_weekly_loss_limit: bool = Field(default=True, description="Block new trades when weekly PnL exceeds max_weekly_loss_pct. 0=OFF.")
    weekly_max_loss_pct: float = Field(default=10.0, ge=1.0, le=50.0, description="Max weekly loss as % of account balance before halting trading.")

    # Monthly loss limit
    enable_monthly_loss_limit: bool = Field(default=True, description="Block new trades when monthly PnL exceeds monthly_max_loss_pct.")
    monthly_max_loss_pct: float = Field(default=8.0, ge=1.0, le=50.0, description="Max monthly loss as % of account balance. 8%=FTMO max drawdown default.")

    # Consecutive loss circuit breaker
    max_consecutive_losses: int = Field(default=3, ge=0, le=10, description="Pause trading after N consecutive losing trades. 0=OFF.")
    consec_loss_pause_hours: float = Field(default=4.0, ge=0.5, le=48.0, description="Hours to pause after hitting consecutive loss limit.")

    # Profit lock-in scaling (protect daily gains)
    enable_profit_lockdown: bool = Field(default=True, description="Reduce position size once daily profit reaches thresholds.")
    profit_lockdown_threshold_1: float = Field(default=0.02, ge=0.005, le=0.2, description="+2% daily profit → scale down to reduction_1 size.")
    profit_lockdown_reduction_1: float = Field(default=0.75, ge=0.1, le=1.0, description="Size multiplier at profit threshold 1 (e.g. 0.75 = 75%).")
    profit_lockdown_threshold_2: float = Field(default=0.03, ge=0.005, le=0.2, description="+3% daily profit → scale down to reduction_2 size.")
    profit_lockdown_reduction_2: float = Field(default=0.5, ge=0.1, le=1.0, description="Size multiplier at profit threshold 2 (e.g. 0.5 = 50%).")

    # Spread gate (minimum SL pips per instrument type)
    spread_gate_enabled: bool = Field(default=True, description="Reject trades where SL is too tight relative to typical spread.")
    min_sl_pips_forex: float = Field(default=3.0, ge=0.5, le=50.0, description="Min SL pips for standard forex pairs.")
    min_sl_pips_jpy: float = Field(default=3.0, ge=0.5, le=50.0, description="Min SL pips for JPY pairs (wider spreads).")
    min_sl_pips_gold: float = Field(default=30.0, ge=1.0, le=500.0, description="Min SL pips for XAUUSD/XAGUSD.")
    min_sl_pips_indices: float = Field(default=10.0, ge=1.0, le=200.0, description="Min SL points for indices (US30, NAS100, SPX500).")

    # Shadow launch toggle for EnsembleBrain gating in worker
    run_shadow_mode: bool = False

    # External execution via MetaApi (MT5 over HTTP)
    meta_api_token: str = ""
    meta_api_account_id: str = ""
    meta_api_accounts: str = Field(default="", description="Comma-separated List of token|account_id pairs for multi-account broadcasting")
    # Optional: JSON array of {name, account_id, token_env_key, risk_pct, max_positions, run_mode} for multi-account (Package A)
    broker_profiles_json: str = Field(default="", description="BROKER_PROFILES_JSON: optional list of broker profiles for one-signal-many-accounts")
    meta_api_region: str = Field(
        default="london",
        description="MetaApi region slug (e.g. 'new-york', 'london', 'singapore'). Must match account region in MetaAPI dashboard.",
        validation_alias="META_API_REGION",
    )
    execution_mode: str = "SHADOW"  # SHADOW | METAAPI (or others in future)

    usdjpy_rate: float = Field(default=150.0, ge=50.0, le=300.0)
    us30_point_value: float = Field(default=1.0, ge=0.1, le=100.0)
    nas100_point_value: float = Field(default=1.0, ge=0.1, le=100.0)

    # ── Evaluation Mode (Prop Firm Challenge Tracking) ──────────────────────
    # IMPORTANT: Set evaluation_mode=True in .env when running a prop firm challenge.
    # All phase limits below are FTMO Standard $50k defaults. Override per-challenge via .env.
    evaluation_mode: bool = Field(default=False, description="Enable prop firm evaluation tracking")
    evaluation_phase: Literal["phase1", "phase2", "funded"] = Field(default="phase1", description="Current evaluation phase")
    evaluation_start_date: str = Field(default="", description="ISO datetime when evaluation started (YYYY-MM-DD)")

    # Phase 1 Rules (FTMO Standard $50k: 10% profit target, 5% max daily loss, 10% max overall DD)
    # Bot operates at 80% of firm limits to leave a safety buffer before hard breach.
    # FTMO rule: max daily loss = 5% of INITIAL balance = $2,500 on $50k
    # Bot kill at: $2,000 (4% of $50k) — leaves $500 buffer before firm breach
    phase1_profit_target: float = Field(default=5000.0, ge=0.0, description="Phase 1 profit target ($). FTMO $50k: $5,000")
    phase1_max_daily_loss: float = Field(default=2000.0, ge=0.0, description="Phase 1 bot kill daily loss ($). FTMO $50k limit=$2500, bot kills at $2000 (80% of limit)")
    phase1_max_drawdown_pct: float = Field(default=8.0, ge=0.0, le=100.0, description="Phase 1 bot kill drawdown (%). FTMO $50k limit=10%, bot kills at 8%")
    phase1_min_trading_days: int = Field(default=4, ge=0, description="Phase 1 minimum trading days")

    # Phase 2 Rules (FTMO Standard $50k: 5% profit target, same loss limits)
    phase2_profit_target: float = Field(default=2500.0, ge=0.0, description="Phase 2 profit target ($). FTMO $50k: $2,500")
    phase2_max_daily_loss: float = Field(default=2000.0, ge=0.0, description="Phase 2 bot kill daily loss ($). Same as Phase 1")
    phase2_max_drawdown_pct: float = Field(default=8.0, ge=0.0, le=100.0, description="Phase 2 bot kill drawdown (%). Same as Phase 1")
    phase2_min_trading_days: int = Field(default=4, ge=0, description="Phase 2 minimum trading days")

    # Funded Account Rules (FTMO: 5% daily loss, 10% trailing DD — bot kills at 80% of each)
    funded_max_daily_loss: float = Field(default=2000.0, ge=0.0, description="Funded account bot kill daily loss ($). FTMO limit=$2500, bot kills at $2000")
    funded_max_drawdown_pct: float = Field(default=8.0, ge=0.0, le=100.0, description="Funded account bot kill drawdown (%). FTMO trailing DD=10%, bot kills at 8%")

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

    # ── Market Holiday Guard ──────────────────────────────────────────────
    enable_holiday_guard: bool = Field(default=True, description="Block US index trades on exchange holidays (Good Friday, MLK Day, etc.)")
    holiday_block_early_close: bool = Field(default=False, description="Also block trades on early-close days (Jul 3, Black Friday, Dec 24)")
    holiday_early_close_utc_hour: int = Field(default=18, ge=12, le=23, description="UTC hour after which to block on early-close days (18 = 1PM ET)")

    # ── Swap / Rollover Guard ─────────────────────────────────────────────
    enable_swap_guard: bool = Field(default=True, description="Block new entries and close positions around broker rollover time")
    swap_time: str = Field(default="00:00", description="Broker rollover time in HH:MM format (server time)")
    swap_timezone: str = Field(default="Asia/Jerusalem", description="Timezone for swap_time (e.g. Asia/Jerusalem, UTC, Europe/Athens)")
    swap_close_before_min: int = Field(default=15, ge=1, le=60, description="Minutes before swap to close all open positions")
    swap_block_after_min: int = Field(default=15, ge=1, le=60, description="Minutes after swap to block new entries")

    # ── Breakeven & Trailing Stop Optimization (v1.1 Phase 9) ─────────────
    breakeven_buffer_pips: float = Field(
        default=3.0, ge=0.0, le=20.0,
        description="Pips above entry (buys) / below entry (sells) when moving SL to breakeven. Env: BREAKEVEN_BUFFER_PIPS.",
        validation_alias="BREAKEVEN_BUFFER_PIPS",
    )
    trail_distance_pips_forex: float = Field(
        default=15.0, ge=1.0, le=200.0,
        description="Trailing stop distance in pips for standard forex pairs (EURUSD, GBPUSD, etc.). Env: TRAIL_DISTANCE_PIPS_FOREX.",
        validation_alias="TRAIL_DISTANCE_PIPS_FOREX",
    )
    trail_distance_points_indices: float = Field(
        default=30.0, ge=1.0, le=500.0,
        description="Trailing stop distance in points for index CFDs (NAS100, US30, UK100, etc.). Env: TRAIL_DISTANCE_POINTS_INDICES.",
        validation_alias="TRAIL_DISTANCE_POINTS_INDICES",
    )
    trail_distance_pips_gold: float = Field(
        default=50.0, ge=1.0, le=500.0,
        description="Trailing stop distance in pips for XAUUSD/GOLD (wider due to volatility). Env: TRAIL_DISTANCE_PIPS_GOLD.",
        validation_alias="TRAIL_DISTANCE_PIPS_GOLD",
    )
    trail_activation_pips: float = Field(
        default=0.0, ge=0.0, le=100.0,
        description="Minimum pips from entry before trailing starts after BE. 0 = trail immediately from BE level. Env: TRAIL_ACTIVATION_PIPS.",
        validation_alias="TRAIL_ACTIVATION_PIPS",
    )

    # ── Consistency Analyzer Settings (Prop Firm Compliance) ──────────────
    consistency_enabled: bool = Field(default=True, description="Enable consistency analyzer (FTMO 40% rule)")
    consistency_limit_pct: float = Field(default=40.0, ge=20.0, le=60.0, description="Max % of total profit from single day (FTMO: 40%)")

    # ── Daily Performance Digest ──────────────────────────────────────────────
    digest_enabled: bool = Field(default=True, description="Enable automated daily performance summary digests.")
    digest_time_utc: str = Field(default="21:00", description="Time (HH:MM UTC) to schedule the daily digest broadcast.", validation_alias="DIGEST_TIME_UTC")

    # ── Signal Transport ──────────────────────────────────────────────────────
    signal_transport: Literal["redis", "memory"] = Field(
        default="redis",
        description="Signal queue backend: 'redis' (production) or 'memory' (tests).",
        validation_alias="SIGNAL_TRANSPORT",
    )
    tradingview_app_path: str = Field(
        default="/Applications/TradingView.app",
        description="Local TradingView Desktop app bundle path used for version detection.",
        validation_alias="TRADINGVIEW_APP_PATH",
    )
    tradingview_allowed_versions: str = Field(
        default="",
        description="Comma-separated exact TradingView Desktop versions approved for chart-context MCP usage.",
        validation_alias="TRADINGVIEW_ALLOWED_VERSIONS",
    )
    tradingview_mcp_compatibility_ttl_seconds: int = Field(
        default=60,
        ge=1,
        le=3600,
        description="Seconds to cache TradingView MCP compatibility results before re-probing.",
        validation_alias="TRADINGVIEW_MCP_COMPATIBILITY_TTL_SECONDS",
    )

    @property
    def live_trading_enabled(self) -> bool:
        """True when run_mode is LIVE (controlled by system_config.trading_mode in DB)."""
        return self.run_mode == "LIVE"

    @property
    def get_accounts(self) -> list[dict]:
        """Parsed list of enabled MetaApi accounts from the META_API_ACCOUNTS string."""
        accounts = []
        if self.meta_api_accounts:
            for pair in self.meta_api_accounts.split(","):
                parts = pair.split("|")
                if len(parts) == 2:
                    accounts.append({"token": parts[0].strip(), "account_id": parts[1].strip()})
        else:
            if self.meta_api_token and self.meta_api_account_id:
                accounts.append({"token": self.meta_api_token, "account_id": self.meta_api_account_id})
        return accounts

    @property
    def tradingview_allowed_version_set(self) -> set[str]:
        """Parsed exact-version allowlist for the local TradingView Desktop app."""
        return {
            item.strip()
            for item in self.tradingview_allowed_versions.split(",")
            if item.strip()
        }


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
