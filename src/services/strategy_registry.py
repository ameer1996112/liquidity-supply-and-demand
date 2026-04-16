from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.adapters.supabase_api import get_api_supabase
from src.services.strategy_config import StrategyConfig, validate_strategy_config


class StrategyRegistryError(RuntimeError):
    """Base error for strategy resolution failures."""


class UnknownStrategyError(StrategyRegistryError):
    """Raised when the requested strategy slug does not exist."""


class InactiveStrategyError(StrategyRegistryError):
    """Raised when the strategy exists but is inactive."""


class StrategyVersionMismatchError(StrategyRegistryError):
    """Raised when the requested version does not match the active row."""


@dataclass(frozen=True)
class ResolvedStrategy:
    """Fully resolved strategy row plus typed config."""

    record_id: int
    strategy_id: str
    strategy_version: str
    name: str
    config: StrategyConfig
    is_active: bool


def resolve_strategy_or_raise(
    *,
    strategy_id: str,
    strategy_version: str,
    supabase: Any | None = None,
) -> ResolvedStrategy:
    """Resolve a strategy row by slug and expected version."""

    sb = supabase or get_api_supabase()
    resp = (
        sb.table("strategy_configs")
        .select("id, slug, name, version, is_active, config")
        .eq("slug", strategy_id)
        .limit(1)
        .execute()
    )
    row = (resp.data or [None])[0]
    if not row:
        raise UnknownStrategyError(strategy_id)
    if not row.get("is_active"):
        raise InactiveStrategyError(strategy_id)

    actual_version = str(row.get("version") or "")
    expected_version = str(strategy_version)
    if actual_version != expected_version:
        raise StrategyVersionMismatchError(
            f"strategy '{strategy_id}' version mismatch: expected {expected_version}, got {actual_version}"
        )

    config = validate_strategy_config(row.get("config") or {})
    return ResolvedStrategy(
        record_id=int(row["id"]),
        strategy_id=str(row["slug"]),
        strategy_version=actual_version,
        name=str(row["name"]),
        config=config,
        is_active=bool(row["is_active"]),
    )
