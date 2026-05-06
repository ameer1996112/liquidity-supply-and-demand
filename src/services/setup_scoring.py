"""Backend setup scoring for RD/S&D strategy signals."""

from __future__ import annotations

from typing import Any

SETUP_SCORE_VERSION = "rd_setup_score_v2"


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _bounded(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _grade(score: float) -> str:
    if score >= 85:
        return "A+"
    if score >= 75:
        return "A"
    if score >= 60:
        return "B"
    if score >= 45:
        return "C"
    return "D"


def _metric_score(payload: dict[str, Any], key: str) -> float:
    value = _as_float(payload.get(key), 0.0)
    if value > 1.0:
        value = value / 100.0
    return _bounded(value)


def _asset_class(symbol: str) -> str:
    normalized = symbol.upper()
    if any(token in normalized for token in ("XAU", "GOLD")):
        return "gold"
    if "JPY" in normalized:
        return "jpy"
    if any(token in normalized for token in ("NAS", "US100", "US30", "SPX", "US500")):
        return "index"
    return "forex"


def _sl_band(asset_class: str, sl_pips: float) -> str:
    if asset_class == "gold":
        if sl_pips <= 50:
            return "gold_0_50"
        if sl_pips <= 100:
            return "gold_50_100"
        if sl_pips <= 150:
            return "gold_100_150"
        if sl_pips <= 200:
            return "gold_150_200"
        return "gold_200_plus"
    if asset_class == "jpy":
        if sl_pips <= 3:
            return "jpy_0_3"
        if sl_pips <= 7:
            return "jpy_3_7"
        if sl_pips <= 11:
            return "jpy_7_11"
        return "jpy_11_plus"
    if sl_pips <= 5:
        return f"{asset_class}_0_5"
    if sl_pips <= 10:
        return f"{asset_class}_5_10"
    if sl_pips <= 20:
        return f"{asset_class}_10_20"
    return f"{asset_class}_20_plus"


def score_rd_setup(payload: dict[str, Any]) -> dict[str, Any]:
    """Return observational RD setup score fields for storage and learning."""
    breakdown: dict[str, dict[str, Any]] = {}
    tags: list[str] = []
    total = 0.0
    strengths: list[str] = []
    weaknesses: list[str] = []

    def add(name: str, points: float, max_points: float, reason: str) -> None:
        nonlocal total
        earned = round(_bounded(points, 0.0, max_points), 2)
        total += earned
        breakdown[name] = {
            "points": earned,
            "max_points": max_points,
            "reason": reason,
        }
        ratio = earned / max_points if max_points else 0.0
        if ratio >= 0.8:
            strengths.append(name)
        elif ratio <= 0.25:
            weaknesses.append(name)

    liq_swept = _as_bool(payload.get("liq_swept") or payload.get("liquidity_sweep"))
    caused_sweep = _as_bool(payload.get("caused_sweep"))
    target_swept = _as_bool(payload.get("target_swept"))
    liq_candles = _as_int(payload.get("liq_candle_count") or payload.get("liquidityCandleCount"), 0)
    sweep_to_touch = payload.get("sweep_to_touch_bars")
    bars_since_zone = _as_int(payload.get("bars_since_zone"), 999)
    entry_model = str(payload.get("entry_model") or "").strip().lower()
    session = _as_int(payload.get("session"), -1)
    rr_ratio = _as_float(payload.get("rr_ratio"), 0.0)
    sl_pips = _as_float(payload.get("sl_pips"), 0.0)
    zone_grade = str(payload.get("zone_grade") or "").strip().upper()
    asset_class = _asset_class(str(payload.get("symbol") or payload.get("ticker") or ""))
    sl_band = _sl_band(asset_class, sl_pips)
    tags.append(f"asset_{asset_class}")
    tags.append(f"sl_band_{sl_band}")

    add("liquidity_sweep", 15.0 if liq_swept else 0.0, 15.0, "Liquidity swept before entry")
    add("caused_sweep", 8.0 if caused_sweep else 0.0, 8.0, "Zone caused/participated in sweep")

    if liq_candles >= 2:
        tags.append("multi_candle_liquidity")
        add("liquidity_structure", min(12.0, 8.0 + liq_candles), 12.0, "Multi-candle liquidity")
    else:
        tags.append("one_candle_liquidity")
        add("liquidity_structure", 0.0, 12.0, "One-candle or missing liquidity")

    if sweep_to_touch is not None:
        bars = _as_int(sweep_to_touch, 999)
        add("sweep_to_touch_timing", 8.0 if 0 <= bars <= 12 else 4.0, 8.0, "Sweep occurred before zone touch")
    else:
        add("sweep_to_touch_timing", 0.0, 8.0, "Sweep timing unknown")

    if target_swept:
        tags.append("target_already_swept")
        weaknesses.append("target_already_swept")
    add("target_room", 5.0 if not target_swept else 0.0, 5.0, "Target liquidity still available")

    model_points = 8.0 if "direction" in entry_model else 6.0 if "break" in entry_model else 5.0 if "flip" in entry_model else 3.0
    if "flip" in entry_model:
        weaknesses.append("flip_entry_model")
    add("entry_model", model_points, 8.0, entry_model or "unknown")

    add("zone_quality", _metric_score(payload, "base_quality") * 10.0, 10.0, "Pine base quality")
    add("departure_strength", _metric_score(payload, "departure_strength") * 10.0, 10.0, "Displacement away from zone")
    add("liquidity_distance", _metric_score(payload, "liquidity_distance") * 7.0, 7.0, "Liquidity distance score")
    add("liquidity_spread", _metric_score(payload, "liquidity_spread") * 5.0, 5.0, "Liquidity spread score")

    freshness_points = 5.0 if bars_since_zone <= 12 else 3.0 if bars_since_zone <= 25 else 1.0
    add("freshness", freshness_points, 5.0, f"bars_since_zone={bars_since_zone}")

    session_points = 5.0 if session in {1, 2} else 3.0 if session == 0 else 1.0
    add("session", session_points, 5.0, f"session={session}")

    rr_points = 4.0 if rr_ratio >= 3.0 else 2.5 if rr_ratio >= 2.0 else 0.5
    add("risk_reward", rr_points, 4.0, f"rr={rr_ratio:.2f}")

    sl_points = 3.0 if 0 < sl_pips <= 11.0 else 1.5 if sl_pips <= 20.0 else 0.5
    add("stop_size", sl_points, 3.0, f"sl_pips={sl_pips:.1f}")

    grade_points = 0.0
    if zone_grade.startswith("A"):
        grade_points = 5.0
    elif zone_grade.startswith("B"):
        grade_points = 3.0
    elif zone_grade:
        grade_points = 1.0
    add("pine_zone_grade", grade_points, 5.0, zone_grade or "unknown")

    if _as_bool(payload.get("is_accuracy")):
        tags.append("accuracy_zone")
        add("accuracy_zone", 3.0, 3.0, "Pine accuracy zone")
    else:
        add("accuracy_zone", 0.0, 3.0, "Not an accuracy zone")

    setup_score = round(_bounded(total, 0.0, 100.0), 1)
    setup_grade = _grade(setup_score)
    tags.append(f"grade_{setup_grade.lower().replace('+', 'plus')}")

    return {
        "setup_score": setup_score,
        "setup_grade": setup_grade,
        "setup_score_version": SETUP_SCORE_VERSION,
        "setup_asset_class": asset_class,
        "setup_sl_band": sl_band,
        "setup_score_breakdown": breakdown,
        "setup_tags": tags,
        "setup_strengths": list(dict.fromkeys(strengths))[:5],
        "setup_weaknesses": list(dict.fromkeys(weaknesses))[:5],
    }
