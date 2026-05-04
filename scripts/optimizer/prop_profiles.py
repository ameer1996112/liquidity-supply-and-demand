from __future__ import annotations

from typing import Any

try:
    from .asset_classifier import is_futures_asset
except ImportError:
    from scripts.optimizer.asset_classifier import is_futures_asset

PROP_PROFILES: dict[str, dict[str, Any]] = {
    "ftmo_2_step_safe": {
        "asset_type": "cfd",
        "daily_loss_pct": 5.0,
        "max_loss_pct": 10.0,
        "safe_daily_loss_pct": 2.5,
        "safe_max_dd_pct": 6.0,
        "risk_per_trade_pct": 0.4,
        "max_trades_per_day": 2,
        "max_symbols_active": 2,
        "max_correlated_symbols": 1,
        "news_blackout_required": True,
    },
    "ftmo_1_step_safe": {
        "asset_type": "cfd",
        "daily_loss_pct": 3.0,
        "max_loss_pct": 6.0,
        "safe_daily_loss_pct": 1.5,
        "safe_max_dd_pct": 3.5,
        "risk_per_trade_pct": 0.25,
        "max_trades_per_day": 1,
        "max_symbols_active": 1,
        "max_correlated_symbols": 1,
        "news_blackout_required": True,
    },
    "the5ers_high_stakes_safe": {
        "asset_type": "cfd",
        "daily_loss_pct": 5.0,
        "max_loss_pct": 10.0,
        "safe_daily_loss_pct": 2.5,
        "safe_max_dd_pct": 6.0,
        "risk_per_trade_pct": 0.4,
        "max_trades_per_day": 2,
        "max_symbols_active": 2,
        "max_correlated_symbols": 1,
        "news_blackout_required": True,
    },
    "generic_cfd_safe": {
        "asset_type": "cfd",
        "daily_loss_pct": 5.0,
        "max_loss_pct": 10.0,
        "safe_daily_loss_pct": 3.0,
        "safe_max_dd_pct": 6.5,
        "risk_per_trade_pct": 0.5,
        "max_trades_per_day": 3,
        "max_symbols_active": 3,
        "max_correlated_symbols": 1,
        "news_blackout_required": True,
    },
    "generic_cfd_ultra_safe": {
        "asset_type": "cfd",
        "daily_loss_pct": 5.0,
        "max_loss_pct": 10.0,
        "safe_daily_loss_pct": 2.0,
        "safe_max_dd_pct": 5.0,
        "risk_per_trade_pct": 0.25,
        "max_trades_per_day": 2,
        "max_symbols_active": 2,
        "max_correlated_symbols": 1,
        "news_blackout_required": True,
    },
    "topstep_50k_safe": {
        "asset_type": "futures",
        "account_size_usd": 50000,
        "max_loss_usd": 2000,
        "safe_max_loss_usd": 1200,
        "daily_loss_usd": None,
        "safe_daily_loss_usd": 700,
        "max_contracts": 2,
        "max_correlated_symbols": 1,
        "max_symbols_active": 2,
        "news_blackout_required": True,
    },
    "custom_cfd_safe": {
        "asset_type": "cfd",
        "daily_loss_pct": 5.0,
        "max_loss_pct": 10.0,
        "safe_daily_loss_pct": 2.5,
        "safe_max_dd_pct": 6.0,
        "risk_per_trade_pct": 0.4,
        "max_trades_per_day": 2,
        "max_symbols_active": 2,
        "max_correlated_symbols": 1,
        "news_blackout_required": True,
    },
    "custom_futures_safe": {
        "asset_type": "futures",
        "account_size_usd": 50000,
        "max_loss_usd": 2000,
        "safe_max_loss_usd": 1200,
        "daily_loss_usd": None,
        "safe_daily_loss_usd": 700,
        "max_contracts": 2,
        "max_correlated_symbols": 1,
        "max_symbols_active": 2,
        "news_blackout_required": True,
    },
}


def _num(params: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(params.get(key, default))
    except (TypeError, ValueError):
        return default


def _int(params: dict[str, Any], key: str, default: int = 0) -> int:
    try:
        return int(params.get(key, default))
    except (TypeError, ValueError):
        return default


def load_prop_profile(profile_name: str) -> dict[str, Any]:
    profile = PROP_PROFILES[profile_name]
    return dict(profile)


def params_pass_prop_profile(
    params: dict[str, Any],
    profile: dict[str, Any],
    symbol: str,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    asset_type = profile.get("asset_type")
    if asset_type == "futures":
        if not is_futures_asset(symbol):
            reasons.append("symbol_not_futures_compatible")
        max_contracts = _int(params, "max_contracts", _int(params, "contracts", 999))
        safe_max_loss = float(profile.get("safe_max_loss_usd") or 0.0)
        safe_daily_loss = float(profile.get("safe_daily_loss_usd") or 0.0)
        estimated_max_loss = _num(params, "estimated_max_loss_usd", _num(params, "max_loss_usd", 999999.0))
        estimated_daily_loss = _num(
            params,
            "estimated_daily_loss_usd",
            _num(params, "daily_loss_usd", 999999.0),
        )
        if max_contracts > int(profile.get("max_contracts", 0)):
            reasons.append(f"max_contracts={max_contracts} > {int(profile['max_contracts'])}")
        if estimated_max_loss > safe_max_loss:
            reasons.append(f"estimated_max_loss_usd={estimated_max_loss:.1f} > {safe_max_loss:.1f}")
        if estimated_daily_loss > safe_daily_loss:
            reasons.append(f"estimated_daily_loss_usd={estimated_daily_loss:.1f} > {safe_daily_loss:.1f}")
    else:
        risk = _num(params, "risk_per_trade_pct", _num(params, "risk_pct", 999.0))
        max_daily = _num(params, "max_daily_loss_pct", 999.0)
        daily_kill = _num(params, "daily_kill_pct", 999.0)
        total_kill = _num(params, "total_kill_pct", 999.0)
        max_trades = _int(params, "max_trades_per_day", 999)
        safe_daily = float(profile.get("safe_daily_loss_pct") or 0.0)
        if risk > float(profile.get("risk_per_trade_pct") or 0.0):
            reasons.append(f"risk_per_trade_pct={risk:g} > {float(profile['risk_per_trade_pct']):g}")
        if max_daily > safe_daily:
            reasons.append(f"max_daily_loss_pct={max_daily:g} > {safe_daily:g}")
        if daily_kill > safe_daily + 0.5:
            reasons.append(f"daily_kill_pct={daily_kill:g} > {safe_daily + 0.5:g}")
        if total_kill > float(profile.get("safe_max_dd_pct") or 0.0):
            reasons.append(f"total_kill_pct={total_kill:g} > {float(profile['safe_max_dd_pct']):g}")
        if max_trades > int(profile.get("max_trades_per_day", 0)):
            reasons.append(f"max_trades_per_day={max_trades} > {int(profile['max_trades_per_day'])}")
    if profile.get("news_blackout_required") and not bool(params.get("news_blackout_enabled")):
        reasons.append("news_blackout_enabled_required")
    return len(reasons) == 0, reasons
