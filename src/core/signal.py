"""Data models for trade signals (webhook payloads)."""

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class ExitWebhookPayload(BaseModel):
    """Payload for trade exit events."""

    model_config = {"extra": "allow"}

    event_type: Literal["exit"] = Field(..., description="Must be 'exit'")
    zone_id: int = Field(..., description="Zone ID to update")
    outcome: str = Field(..., description="win, loss, breakeven")
    bars_held: int = Field(..., description="Bars position was held")
    close_price: float = Field(..., description="Exit price")
    exit_type: str = Field(..., description="tp, sl, etc.")
    mae_pips: float = Field(..., description="Max adverse excursion in pips")


class EntryWebhookPayload(BaseModel):
    """Payload for trade entry / signal events."""

    model_config = {"extra": "allow"}

    strategy_id: str = Field(
        ...,
        min_length=1,
        description="Canonical strategy slug from strategy_configs.slug",
    )
    strategy_version: str = Field(
        ...,
        min_length=1,
        description="Expected active strategy version",
    )
    symbol: str = Field(..., min_length=1, description="Instrument symbol")
    side: str = Field(..., description="buy or sell")
    entry: float = Field(..., description="Entry price")
    sl: float = Field(..., description="Stop loss price")
    tp: float = Field(..., description="Take profit price")
    size: float = Field(..., description="Position size")

    # Sprint 6.2: Advanced TradingView strategy vocabulary
    # Optional high-level action and execution hints. These are intentionally
    # loose (str/Any) to remain backwards compatible with older alerts and to
    # allow future Pine Script variants without breaking validation.
    action: str | None = Field(
        default=None,
        description="High-level intent: entry|exit|close_all|modify|cancel (optional)",
    )
    order_type: str | None = Field(
        default=None,
        description="Order type hint: market|limit|stop (optional)",
    )
    trailing_stop: Any | None = Field(
        default=None,
        description="Trailing stop configuration or flag (optional)",
    )
    multi_tp: list[float] | None = Field(
        default=None,
        description="Additional take profit levels (optional)",
    )
    partial_close_percent: float | None = Field(
        default=None,
        description="Partial close percentage 0-100 (optional)",
    )
    force_live_override: bool = Field(
        default=False,
        description="Set true to allow live MetaTrader execution from non-TradingView sources (manual override)",
    )

    event_type: str | None = Field(None, description="If 'exit', use exit payload instead")
    signal_time: str | None = Field(None, description="Original signal generation time (UTC)")

    # Phase 12: TradingView S&D Algo fields — passed in Pine Script alerts
    bar_time: str | None = Field(None, description="Bar open time (UTC) used for staleness check")
    zone_id: int | None = Field(None, description="S&D zone ID from Pine Script — links entry to exit")
    rr_ratio: float | None = Field(None, description="Risk:Reward ratio from Pine Script — checked against min_rr_ratio")
    run_mode: str | None = Field(None, description="Override run mode: LIVE or PAPER (optional, resolved by API if absent)")

    # Backend entry execution refinements. These let TradingView describe the
    # signal bar, while MetaTrader waits for a spread-aware executable price.
    execution_mode: Literal["market_on_signal", "wait_for_next_wick"] | None = Field(
        default="market_on_signal",
        description="Backend execution mode for entries",
    )
    entry_reference_price: float | None = Field(
        default=None,
        description="Reference close/entry price used for pending pullback execution",
    )
    wick_entry_pullback_pips: float | None = Field(
        default=None,
        description="Required bid/ask pullback before live entry",
    )
    max_entry_delay_seconds: float | None = Field(
        default=None,
        description="Maximum seconds to wait for pending entry mitigation",
    )
    entry_poll_interval_seconds: float | None = Field(
        default=None,
        description="Seconds between price checks during pending entry",
    )
    max_spread_pips: float | None = Field(
        default=None,
        description="Maximum allowed live spread at pending entry trigger",
    )

    # Backend-generated observational score. This is for learning/reporting,
    # not a hard execution gate.
    setup_score: float | None = Field(default=None, description="Backend RD setup score 0-100")
    setup_grade: str | None = Field(default=None, description="Backend RD setup grade")
    setup_score_version: str | None = Field(default=None, description="Backend RD setup score model version")
    setup_asset_class: str | None = Field(default=None, description="Backend setup scoring asset class")
    setup_sl_band: str | None = Field(default=None, description="Backend setup scoring SL-size band")
    setup_score_breakdown: dict[str, Any] | None = Field(
        default=None,
        description="Backend RD setup score contribution details",
    )
    setup_tags: list[str] | None = Field(default=None, description="Backend RD setup learning tags")
    setup_strengths: list[str] | None = Field(default=None, description="Top backend setup scoring strengths")
    setup_weaknesses: list[str] | None = Field(default=None, description="Top backend setup scoring weaknesses")

    @model_validator(mode="after")
    def side_must_be_buy_or_sell(self) -> "EntryWebhookPayload":
        if str(self.side).lower() not in ("buy", "sell"):
            raise ValueError("side must be 'buy' or 'sell'")
        return self

    @model_validator(mode="after")
    def rd_forex_lifecycle_events_are_not_executable(self) -> "EntryWebhookPayload":
        event = str(self.event_type or self.action or "").strip().upper()
        strategy = str(self.strategy_id or "").strip().lower()
        version = str(self.strategy_version or "").strip().upper()
        is_rd_forex = strategy in {"rd_forex", "rd_forex_zone_detector"} or version.startswith("LAB_PHASE0")
        if is_rd_forex and event != "TRADE_ELIGIBLE_EXECUTABLE":
            raise ValueError("RD Forex lifecycle/debug events are not executable webhook payloads")
        return self


class RdForexDebugEventPayload(BaseModel):
    """Non-execution RD Forex LAB lifecycle/debug event schema."""

    model_config = {"extra": "allow"}

    event: Literal[
        "ZONE_CANDIDATE",
        "ZONE_CONFIRMED_NON_EXECUTABLE",
        "LIQUIDITY_LINKED",
        "ZONE_TOUCHED",
        "ZONE_INVALIDATED",
        "LIQUIDITY_SWEPT",
        "TARGET_SWEPT",
    ]
    run_id: str = Field(..., min_length=1)
    symbol: str = Field(..., min_length=1)
    timeframe: str = Field(..., min_length=1)
    zone_id: int
    model: str = Field(..., min_length=1)
    zone_type: Literal["demand", "supply"]
    origin_bar: int
    origin_time: int | None = None
    detection_bar: int | None = None
    detection_time: int | None = None
    confirmation_bar: int | None = None
    top: float
    bottom: float
    active: bool | None = None
    liquidity_price: float | None = None
    liquidity_bar_index: int | None = None
    liquidity_swept: bool | None = None
    target_swept: bool | None = None
    touched: bool | None = None
    invalidation_reason: str | None = None


def validate_webhook_payload(data: dict[str, Any]) -> dict[str, Any]:
    """
    Validate parsed body as either Entry or Exit payload.
    Returns the same dict; raises pydantic.ValidationError on failure.
    """
    if not data or not isinstance(data, dict):
        raise ValueError("Empty or invalid body")

    event_type = (data.get("event_type") or "").strip().lower()
    action = (str(data.get("action") or "")).strip().lower()

    # Sprint 6.2: allow either legacy event_type="exit" or new action="exit"
    # to route into the ExitWebhookPayload, keeping backwards compatibility.
    if event_type == "exit" or action == "exit":
        ExitWebhookPayload.model_validate(data)
    else:
        EntryWebhookPayload.model_validate(data)
    return data


def validate_rd_forex_debug_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Validate a non-executable RD Forex LAB debug/lifecycle event."""
    if not data or not isinstance(data, dict):
        raise ValueError("Empty or invalid body")
    RdForexDebugEventPayload.model_validate(data)
    return data
