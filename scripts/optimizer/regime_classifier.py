from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

try:
    from .config import RESULTS_DIR
except ImportError:
    from scripts.optimizer.config import RESULTS_DIR

REGIME_SNAPSHOT_FILE = RESULTS_DIR / "regime_snapshots.json"


@dataclass
class RegimeSnapshot:
    symbol: str
    timestamp: str
    regimes: list[str]
    atr_percentile: float | None
    trend_strength: float | None
    volatility_state: str
    session_state: str
    spread_state: str
    news_state: str
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _true_ranges(candles: list[dict[str, Any]]) -> list[float]:
    ranges: list[float] = []
    previous_close: float | None = None
    for candle in candles:
        high = float(candle.get("high", candle.get("close", 0)) or 0)
        low = float(candle.get("low", candle.get("close", 0)) or 0)
        close = float(candle.get("close", 0) or 0)
        if previous_close is None:
            ranges.append(max(high - low, 0.0))
        else:
            ranges.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
        previous_close = close
    return ranges


def classify_regime(
    symbol: str,
    *,
    candles: list[dict[str, Any]] | None = None,
    manual_state: dict[str, Any] | None = None,
) -> RegimeSnapshot:
    if manual_state:
        return RegimeSnapshot(
            symbol=symbol.upper(),
            timestamp=str(manual_state.get("timestamp") or _now()),
            regimes=list(manual_state.get("regimes") or ["UNKNOWN"]),
            atr_percentile=manual_state.get("atr_percentile"),
            trend_strength=manual_state.get("trend_strength"),
            volatility_state=str(manual_state.get("volatility_state") or "UNKNOWN"),
            session_state=str(manual_state.get("session_state") or "UNKNOWN"),
            spread_state=str(manual_state.get("spread_state") or "UNKNOWN"),
            news_state=str(manual_state.get("news_state") or "UNKNOWN"),
            confidence=float(manual_state.get("confidence", 0.25)),
        )

    candles = candles or []
    if len(candles) < 10:
        return RegimeSnapshot(symbol.upper(), _now(), ["UNKNOWN"], None, None, "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", 0.0)

    closes = [float(candle.get("close", 0) or 0) for candle in candles]
    start = closes[0]
    end = closes[-1]
    trend_strength = (end - start) / max(abs(start), 1.0)
    ranges = _true_ranges(candles)
    recent_atr = mean(ranges[-10:])
    long_atr = mean(ranges)
    atr_ratio = recent_atr / max(long_atr, 0.000001)
    atr_percentile = max(0.0, min(100.0, atr_ratio * 50.0))
    regimes: list[str] = []
    if trend_strength > 0.03:
        regimes.append("TRENDING_UP")
    elif trend_strength < -0.03:
        regimes.append("TRENDING_DOWN")
    else:
        regimes.append("RANGING")
    if atr_ratio >= 1.3:
        regimes.extend(["HIGH_VOLATILITY", "VOLATILITY_EXPANSION"])
        volatility_state = "VOLATILITY_EXPANSION"
    elif atr_ratio <= 0.75:
        regimes.extend(["LOW_VOLATILITY", "VOLATILITY_COMPRESSION"])
        volatility_state = "VOLATILITY_COMPRESSION"
    else:
        volatility_state = "NORMAL"
    regimes.append("SESSION_OK")
    return RegimeSnapshot(
        symbol.upper(),
        _now(),
        regimes,
        atr_percentile,
        trend_strength,
        volatility_state,
        "SESSION_OK",
        "OK",
        "OK",
        min(0.9, 0.45 + abs(trend_strength) * 5.0),
    )


def load_manual_snapshots(path: Path) -> dict[str, RegimeSnapshot]:
    payload = json.loads(path.read_text()) if path.exists() else {}
    return {
        str(symbol).upper(): classify_regime(str(symbol), manual_state=row)
        for symbol, row in payload.items()
        if isinstance(row, dict)
    }


def write_regime_snapshots(snapshots: dict[str, RegimeSnapshot], path: Path = REGIME_SNAPSHOT_FILE) -> dict[str, Any]:
    payload = {
        "schema_version": 1,
        "created_at": _now(),
        "source_files": [],
        "prop_profile": None,
        "status": "completed",
        "rejection_reasons": {},
        "warnings": [],
        "snapshots": {symbol: snapshot.to_dict() for symbol, snapshot in snapshots.items()},
    }
    path.write_text(json.dumps(payload, indent=2))
    return payload
