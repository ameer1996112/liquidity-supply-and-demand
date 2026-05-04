from __future__ import annotations

from typing import Any


WINDOW_DAYS = {"365d": 365.0, "90d": 90.0, "30d": 30.0}
TRADE_COUNT_ANOMALY_RATE_RATIO = 5.0


def _metric(row: dict[str, Any], key: str) -> float | None:
    try:
        return float(row[key])
    except (KeyError, TypeError, ValueError):
        return None


def _truth_explains_anomaly(row: dict[str, Any]) -> bool:
    truth = row.get("result_truth")
    evidence = truth.get("evidence") if isinstance(truth, dict) else {}
    anomaly = (evidence or {}).get("trade_count_anomaly_explained") or {}
    return anomaly.get("status") == "ok"


def detect_trade_count_anomaly(
    rows: dict[str, dict[str, Any]],
    *,
    rate_ratio_threshold: float = TRADE_COUNT_ANOMALY_RATE_RATIO,
) -> dict[str, Any] | None:
    """Detect unexplained cross-window trade-density anomalies."""
    rates: list[tuple[str, int, float, float]] = []
    for window, row in rows.items():
        trades = _metric(row, "total_trades")
        if trades is None or trades <= 0:
            continue
        days = WINDOW_DAYS.get(window, 1.0)
        truth = row.get("result_truth")
        if isinstance(truth, dict):
            evidence = truth.get("evidence") or {}
            range_details = (evidence.get("strategy_tester_range_selected") or {}).get("details") or {}
            try:
                days = float(range_details.get("requested_days") or days)
            except (TypeError, ValueError):
                pass
        rates.append((window, int(trades), days, float(trades) / max(days, 1.0)))

    if len(rates) < 2:
        return None

    low = min(rates, key=lambda item: item[3])
    high = max(rates, key=lambda item: item[3])
    raw_counts = [item[1] for item in rates]
    raw_ratio = max(raw_counts) / max(min(raw_counts), 1)
    rate_ratio = high[3] / low[3] if low[3] > 0 else 0.0
    if rate_ratio < rate_ratio_threshold or raw_ratio < 2.0:
        return None
    if any(_truth_explains_anomaly(row) for row in rows.values()):
        return None

    return {
        "status": "unexplained",
        "high_window": high[0],
        "high_trades": high[1],
        "high_days": high[2],
        "low_window": low[0],
        "low_trades": low[1],
        "low_days": low[2],
        "rate_ratio": rate_ratio,
        "reason": (
            "trade_count_anomaly_unexplained:"
            f"{high[0]}={high[1]} trades/{high[2]:.0f}d vs "
            f"{low[0]}={low[1]} trades/{low[2]:.0f}d "
            f"(rate_ratio={rate_ratio:.1f}x)"
        ),
    }
