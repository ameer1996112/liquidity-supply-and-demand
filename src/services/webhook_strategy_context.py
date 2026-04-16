from __future__ import annotations

from typing import Any, Callable

from src.services.strategy_registry import (
    InactiveStrategyError,
    StrategyVersionMismatchError,
    UnknownStrategyError,
    resolve_strategy_or_raise,
)


class StrategyContextError(RuntimeError):
    """Strategy identity could not be resolved for an entry alert."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


def resolve_and_stamp_strategy_context(
    payload: dict[str, Any],
    *,
    resolver: Callable[..., Any] = resolve_strategy_or_raise,
) -> dict[str, Any]:
    """Resolve strategy identity for entry alerts and stamp trusted context."""
    event_type = (payload.get("event_type") or "").strip().lower()
    action = (str(payload.get("action") or "")).strip().lower()
    is_exit = event_type == "exit" or action == "exit"
    if is_exit:
        return payload

    try:
        resolved = resolver(
            strategy_id=str(payload.get("strategy_id") or ""),
            strategy_version=str(payload.get("strategy_version") or ""),
        )
    except UnknownStrategyError as exc:
        raise StrategyContextError("unknown_strategy") from exc
    except InactiveStrategyError as exc:
        raise StrategyContextError("inactive_strategy") from exc
    except StrategyVersionMismatchError as exc:
        raise StrategyContextError("strategy_version_mismatch") from exc

    payload["strategy_id"] = resolved.strategy_id
    payload["strategy_version"] = resolved.strategy_version
    payload["strategy_name"] = resolved.name
    payload["strategy_config_id"] = resolved.record_id
    payload["strategy_config_snapshot"] = resolved.config.model_dump()
    return payload


def build_received_signal_row(
    payload: dict[str, Any],
    *,
    run_mode: str,
    account_id: str,
    receipt_id: str,
    account_balance: float,
) -> dict[str, Any]:
    """Build the API-level 'received' trading_signals row for entry alerts."""
    row = {
        "symbol": payload.get("symbol", "UNKNOWN"),
        "side": payload.get("side", "buy"),
        "size": float(payload.get("size", 0.01)),
        "entry": float(payload.get("entry", 0)) if payload.get("entry") else None,
        "sl": float(payload.get("sl", 0)) if payload.get("sl") else None,
        "tp": float(payload.get("tp", 0)) if payload.get("tp") else None,
        "status": "received",
        "notes": "Received by API, awaiting worker",
        "run_mode": run_mode,
        "account_id": account_id,
        "webhook_receipt_id": receipt_id,
        "account_balance": account_balance,
        "strategy_id": payload.get("strategy_id"),
        "strategy_version": payload.get("strategy_version"),
        "strategy_name": payload.get("strategy_name"),
        "strategy_config_id": payload.get("strategy_config_id"),
    }
    if payload.get("trade_key"):
        row["trade_key"] = payload["trade_key"]
    return row
