"""
Sprint 4.4: Strategy-as-data configuration.

Defines the strategy config schema (signal filters, risk rules presets,
AI/debate settings, execution routing) and validation helpers.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ValidationError, field_validator

logger = logging.getLogger(__name__)


class SignalFilters(BaseModel):
    """Signal-level filters for symbols and sessions."""

    symbols: List[str] = Field(
        default_factory=list,
        description="Optional whitelist of symbols (e.g. ['XAUUSD', 'NAS100']). Empty = all symbols.",
    )
    exclude_symbols: List[str] = Field(
        default_factory=list,
        description="Optional blacklist of symbols that must never trade.",
    )
    sessions: List[str] = Field(
        default_factory=list,
        description="Trading sessions to allow: asian|london|ny|off",
    )

    @field_validator("symbols", "exclude_symbols", mode="before")
    @classmethod
    def _normalize_symbols(cls, v: Any) -> Any:
        if v is None:
            return []
        if isinstance(v, str):
            return [v.upper()]
        if isinstance(v, list):
            return [str(s).upper() for s in v]
        raise TypeError("symbols/exclude_symbols must be string or list of strings")

    @field_validator("sessions", mode="before")
    @classmethod
    def _normalize_sessions(cls, v: Any) -> Any:
        if v is None:
            return []
        if isinstance(v, str):
            v = [v]
        if isinstance(v, list):
            norm = [str(s).lower() for s in v]
            allowed = {"asian", "london", "ny", "off"}
            invalid = [s for s in norm if s not in allowed]
            if invalid:
                raise ValueError(
                    f"Invalid session values {invalid}; allowed: {sorted(allowed)}"
                )
            return norm
        raise TypeError("sessions must be string or list of strings")


class RiskPreset(BaseModel):
    """Risk rules preset for a strategy."""

    name: str = Field(
        default="balanced",
        description="Human label, e.g. conservative|balanced|aggressive|custom",
    )
    risk_percent: float = Field(
        default=0.5,
        ge=0.0,
        le=5.0,
        description="Per-trade risk percent to target (overrides Settings.risk_percent).",
    )
    min_rr_ratio: float = Field(
        default=0.0,
        ge=0.0,
        le=10.0,
        description="Minimum R:R ratio; 0 = follow global/min_rr_ratio.",
    )


class DebateConfig(BaseModel):
    """Debate guardrail configuration."""

    enabled: bool = Field(
        default=True,
        description="Whether to run Bull/Bear/Risk/Chair debate in shadow mode.",
    )
    rounds: int = Field(
        default=1,
        ge=0,
        le=5,
        description="Number of debate rounds (currently informational; debate runs once).",
    )
    min_confidence: int = Field(
        default=60,
        ge=0,
        le=100,
        description="Minimum chair confidence to treat debate as strong signal (informational).",
    )


class AIConfig(BaseModel):
    """AI mode + debate configuration."""

    mode: str = Field(
        default="shadow",
        description="AI enforcement mode: shadow | enforce | off.",
    )
    debate: DebateConfig = Field(
        default_factory=DebateConfig,
        description="Debate guardrail configuration.",
    )

    @field_validator("mode")
    @classmethod
    def _validate_mode(cls, v: str) -> str:
        v_norm = str(v).lower()
        allowed = {"shadow", "enforce", "off"}
        if v_norm not in allowed:
            raise ValueError(f"ai.mode must be one of {sorted(allowed)}, got '{v}'")
        return v_norm


class ExecutionRoutingRule(BaseModel):
    """Execution routing for a specific account / broker profile."""

    account_name: str = Field(
        ...,
        min_length=1,
        description="Logical account name (e.g. 'ftmo-main', 'paper-lab').",
    )
    run_mode: str = Field(
        default="PAPER",
        description="Execution run mode: PAPER | LIVE.",
    )
    broker_profile_id: Optional[int] = Field(
        default=None,
        description="Optional broker_profiles.id for multi-account execution.",
    )
    enabled: bool = Field(
        default=True,
        description="Whether this routing rule is active.",
    )
    risk_multiplier: float = Field(
        default=1.0,
        ge=0.1,
        le=5.0,
        description="Additional risk multiplier applied on top of base risk_percent.",
    )

    @field_validator("run_mode")
    @classmethod
    def _validate_run_mode(cls, v: str) -> str:
        v_norm = str(v).upper()
        allowed = {"PAPER", "LIVE"}
        if v_norm not in allowed:
            raise ValueError(
                f"execution.run_mode must be one of {sorted(allowed)}, got '{v}'"
            )
        return v_norm


class StrategyConfig(BaseModel):
    """
    Top-level strategy configuration.

    This is stored as JSONB in strategy_configs.config.
    """

    name: str = Field(..., min_length=1, description="Human-readable strategy name.")
    signal_filters: SignalFilters = Field(
        default_factory=SignalFilters,
        description="Symbol + session filters.",
    )
    risk: RiskPreset = Field(
        default_factory=RiskPreset,
        description="Risk rules preset.",
    )
    ai: AIConfig = Field(
        default_factory=AIConfig,
        description="AI mode + debate configuration.",
    )
    execution_routing: List[ExecutionRoutingRule] = Field(
        default_factory=list,
        description="Per-account execution routing rules.",
    )

    @field_validator("execution_routing")
    @classmethod
    def _ensure_unique_accounts(cls, v: List[ExecutionRoutingRule]) -> List[ExecutionRoutingRule]:
        seen = set()
        for r in v:
            key = (r.account_name.strip().lower(), r.run_mode.upper())
            if key in seen:
                raise ValueError(
                    f"Duplicate execution routing for account '{r.account_name}' and run_mode '{r.run_mode}'"
                )
            seen.add(key)
        return v


def validate_strategy_config(raw: Dict[str, Any]) -> StrategyConfig:
    """
    Validate a raw config dict and return a typed StrategyConfig.

    Raises:
        pydantic.ValidationError on invalid config.
    """
    if not isinstance(raw, dict):
        raise TypeError("strategy config must be a JSON object")
    return StrategyConfig.model_validate(raw)


def format_validation_errors(err: ValidationError) -> List[Dict[str, Any]]:
    """
    Convert Pydantic ValidationError into a frontend-friendly list.

    Each item contains: loc, message, type.
    """
    errors: List[Dict[str, Any]] = []
    for e in err.errors():
        loc = ".".join(str(part) for part in e.get("loc", ()))
        msg = e.get("msg", "")
        typ = e.get("type", "")
        errors.append({"field": loc, "message": msg, "type": typ})
    return errors


def get_active_strategy(supabase: Any) -> Optional[Dict[str, Any]]:
    """
    Fetch the currently active strategy (if any).

    Returns:
        Dict with keys: id, name, version, config (dict) or None.
    """
    if not supabase:
        return None
    try:
        resp = (
            supabase.table("strategy_configs")
            .select("id, name, version, config")
            .eq("is_active", True)
            .order("updated_at", desc=True)
            .limit(1)
            .execute()
        )
        row = (resp.data or [None])[0]
        if not row:
            return None
        cfg = row.get("config") or {}
        return {
            "id": row.get("id"),
            "name": row.get("name"),
            "version": row.get("version") or 1,
            "config": cfg,
        }
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to fetch active strategy: %s", e)
        return None


def validate_active_strategies_startup(supabase: Any) -> None:
    """
    Validate all active strategies at startup.

    If any active strategy has an invalid config, startup should fail-fast so
    the system does not run with unsafe or inconsistent strategy-as-data.

    Raises:
        RuntimeError: if validation of one or more active strategies fails.
    """
    if not supabase:
        return

    try:
        resp = (
            supabase.table("strategy_configs")
            .select("id, name, config")
            .eq("is_active", True)
            .execute()
        )
        rows = resp.data or []
    except Exception as e:  # noqa: BLE001
        logger.warning("Strategy config validation skipped (query failed): %s", e)
        return

    invalid: list[dict[str, Any]] = []

    for row in rows:
        sid = row.get("id")
        name = row.get("name", f"strategy-{sid}")
        cfg = row.get("config") or {}
        try:
            validate_strategy_config(cfg)
            logger.info("Strategy '%s' (id=%s) validated successfully.", name, sid)
        except ValidationError as ve:
            errs = format_validation_errors(ve)
            logger.error(
                "Invalid strategy config at startup for '%s' (id=%s): %s",
                name,
                sid,
                errs,
            )
            invalid.append(
                {
                    "id": sid,
                    "name": name,
                    "errors": errs,
                }
            )

    if invalid:
        summary = "; ".join(
            f"id={item['id']} name={item['name']} errors={item['errors']!r}"
            for item in invalid
        )
        raise RuntimeError(
            f"Strategy config startup validation failed for {len(invalid)} "
            f"active strateg(ies): {summary}"
        )

