from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .asset_classifier import classify_asset
    from .config import RESULTS_DIR
except ImportError:
    from scripts.optimizer.asset_classifier import classify_asset
    from scripts.optimizer.config import RESULTS_DIR


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _symbol_groups(symbol: str) -> set[str]:
    clean = symbol.upper()
    groups = {classify_asset(clean).upper()}
    if "USD" in clean or clean in {"XAUUSD", "XAGUSD", "NAS100", "US100", "US500", "US30"}:
        groups.add("USD")
    if clean.endswith("JPY"):
        groups.add("JPY")
    return groups


def evaluate_trading_conditions(
    *,
    symbols: list[str],
    news_blackouts: list[dict[str, Any]],
    now: str | None = None,
    spread_states: dict[str, str] | None = None,
    session_states: dict[str, str] | None = None,
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    current = _parse(now) if now else datetime.now(timezone.utc)
    spread_states = {k.upper(): v for k, v in (spread_states or {}).items()}
    session_states = {k.upper(): v for k, v in (session_states or {}).items()}
    profile = profile or {}
    blocked: dict[str, list[str]] = {}
    for symbol in [item.upper() for item in symbols]:
        reasons: list[str] = []
        if spread_states.get(symbol) == "SPREAD_RISK":
            reasons.append("spread risk active")
        if session_states.get(symbol) == "SESSION_BAD":
            reasons.append("outside validated session")
        if profile.get("news_blackout_required", True):
            groups = _symbol_groups(symbol)
            for window in news_blackouts:
                if str(window.get("symbol_group", "")).upper() not in groups:
                    continue
                if _parse(window["start"]) <= current <= _parse(window["end"]):
                    reasons.append(str(window.get("reason") or "news blackout active"))
        if reasons:
            blocked[symbol] = reasons
    return {
        "schema_version": 1,
        "created_at": _now(),
        "source_files": [],
        "prop_profile": profile.get("name"),
        "status": "completed",
        "blocked_symbols": blocked,
        "rejection_reasons": blocked,
        "warnings": [],
    }


def cli(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Evaluate news/session/spread trading conditions.")
    parser.add_argument("--symbols", default="")
    parser.add_argument("--manual-news", default=str(RESULTS_DIR / "manual_news_blackout.json"))
    args = parser.parse_args(argv)
    news_path = Path(args.manual_news)
    payload = json.loads(news_path.read_text()) if news_path.exists() else {"blackout_windows": []}
    report = evaluate_trading_conditions(symbols=[item for item in args.symbols.split(",") if item], news_blackouts=payload.get("blackout_windows", []))
    (RESULTS_DIR / "trading_conditions_report.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    cli()
