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


def _float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _bool_or_none(value: Any) -> bool | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes", "y"}:
        return True
    if normalized in {"false", "0", "no", "n"}:
        return False
    return None


def _drop_none(data: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if value is not None}


def _build_triggered_zone_setup_evidence(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Build a compact evidence bundle for zones that actually fired an entry."""
    zone_id = _int_or_none(payload.get("zone_id"))
    if zone_id is None:
        return None

    zone_top = _float_or_none(payload.get("zone_top"))
    zone_bottom = _float_or_none(payload.get("zone_bottom"))
    zone_type = payload.get("zone_type")
    zone_label = f"{str(zone_type).title()} #{zone_id}" if zone_type else f"Zone #{zone_id}"

    focus_zone = _drop_none(
        {
            "id": zone_id,
            "type": zone_type,
            "high": max(zone_top, zone_bottom) if zone_top is not None and zone_bottom is not None else zone_top,
            "low": min(zone_top, zone_bottom) if zone_top is not None and zone_bottom is not None else zone_bottom,
            "label": zone_label,
            "source": "entry_webhook",
        }
    )
    triggered_zone = {
        "zone": _drop_none(
            {
                "id": zone_id,
                "type": zone_type,
                "top": zone_top,
                "bottom": zone_bottom,
                "grade": payload.get("zone_grade"),
                "score": _float_or_none(payload.get("score")),
                "is_accuracy": _bool_or_none(payload.get("is_accuracy")),
                "entry_model": payload.get("entry_model"),
                "bars_since_zone": _int_or_none(payload.get("bars_since_zone")),
            }
        ),
        "liquidity": _drop_none(
            {
                "swept": _bool_or_none(payload.get("liq_swept")),
                "target_swept": _bool_or_none(payload.get("target_swept")),
                "caused_sweep": _bool_or_none(payload.get("caused_sweep")),
                "distance_pips": _float_or_none(payload.get("liquidity_distance_pips")),
                "spread_pips": _float_or_none(payload.get("liquidity_spread_pips")),
                "score_distance": _float_or_none(payload.get("liquidity_distance")),
                "score_spread": _float_or_none(payload.get("liquidity_spread")),
                "source": payload.get("liq_source"),
                "sweep_to_touch_bars": _int_or_none(payload.get("sweep_to_touch_bars")),
                "peak_to_touch_bars": _int_or_none(payload.get("peak_to_touch_bars")),
            }
        ),
        "signal": _drop_none(
            {
                "trade_key": payload.get("trade_key"),
                "symbol": payload.get("symbol"),
                "side": payload.get("side"),
                "entry": _float_or_none(payload.get("entry")),
                "sl": _float_or_none(payload.get("sl")),
                "tp": _float_or_none(payload.get("tp")),
                "rr_ratio": _float_or_none(payload.get("rr_ratio")),
                "sl_pips": _float_or_none(payload.get("sl_pips")),
                "bar_time": payload.get("bar_time") or payload.get("signal_time"),
            }
        ),
    }

    return {
        "status": "ok",
        "source": "entry_webhook",
        "reason": "triggered zone captured from entry webhook",
        "focus_image": None,
        "focus_zone": focus_zone,
        "triggered_zone": triggered_zone,
    }


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
    triggered_zone_evidence = _build_triggered_zone_setup_evidence(payload)
    if triggered_zone_evidence is not None:
        existing_setup_evidence = payload.get("setup_evidence")
        if isinstance(existing_setup_evidence, dict):
            setup_evidence = {**triggered_zone_evidence, **existing_setup_evidence}
            setup_evidence["triggered_zone"] = triggered_zone_evidence["triggered_zone"]
        else:
            setup_evidence = triggered_zone_evidence
        payload["setup_evidence"] = setup_evidence

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
        "account_name": (
            payload.get("_account_name")
            or payload.get("account_name")
            or account_id
            or "default"
        ),
        "webhook_receipt_id": receipt_id,
        "account_balance": account_balance,
        "strategy_id": payload.get("strategy_id"),
        "strategy_version": payload.get("strategy_version"),
        "strategy_name": payload.get("strategy_name"),
        "strategy_config_id": payload.get("strategy_config_id"),
    }
    zone_id = _int_or_none(payload.get("zone_id"))
    if zone_id is not None:
        row["zone_id"] = zone_id
    if payload.get("trade_key"):
        row["trade_key"] = payload["trade_key"]
    if payload.get("setup_evidence") is not None:
        row["setup_evidence"] = payload["setup_evidence"]

    passthrough_fields = {
        "zone_type": str,
        "entry_model": str,
        "liq_source": str,
        "zone_grade": str,
        "zone_top": _float_or_none,
        "zone_bottom": _float_or_none,
        "zone_size_pips": _float_or_none,
        "rr_ratio": _float_or_none,
        "score": _float_or_none,
        "freshness": _int_or_none,
        "session": _int_or_none,
        "atr_ratio": _float_or_none,
        "trend": _int_or_none,
        "rsi": _float_or_none,
        "htf_trend": _int_or_none,
        "rvol": _float_or_none,
        "adx": _float_or_none,
        "touch_count": _int_or_none,
        "base_quality": _float_or_none,
        "departure_strength": _float_or_none,
        "liquidity_distance": _float_or_none,
        "liquidity_spread": _float_or_none,
        "liquidity_distance_pips": _float_or_none,
        "liquidity_spread_pips": _float_or_none,
        "sl_pips": _float_or_none,
        "sweep_to_touch_bars": _int_or_none,
        "peak_to_touch_bars": _int_or_none,
        "bars_since_zone": _int_or_none,
        "liq_swept": _bool_or_none,
        "target_swept": _bool_or_none,
        "caused_sweep": _bool_or_none,
        "is_accuracy": _bool_or_none,
        "primed": _bool_or_none,
    }
    for field, converter in passthrough_fields.items():
        if payload.get(field) is None:
            continue
        value = converter(payload.get(field))
        if value is not None:
            row[field] = value
    return row
