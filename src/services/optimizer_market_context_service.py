from __future__ import annotations


def _scaled_spread(value: float, multiplier: float) -> float:
    return round(value * multiplier, 10)


def symbol_currencies(symbol: str) -> list[str]:
    normalized_symbol = symbol.upper()
    if (
        len(normalized_symbol) >= 6
        and normalized_symbol[:3].isalpha()
        and normalized_symbol[3:6].isalpha()
    ):
        return [normalized_symbol[:3], normalized_symbol[3:6]]
    return [normalized_symbol]


def build_spread_stress_profiles(
    *,
    baseline_spread: float,
    slippage_per_side: float,
) -> dict[str, dict[str, float]]:
    return {
        "baseline": {
            "spread": baseline_spread,
            "slippage_per_side": slippage_per_side,
        },
        "spread_125": {
            "spread": _scaled_spread(baseline_spread, 1.25),
            "slippage_per_side": slippage_per_side,
        },
        "spread_150": {
            "spread": _scaled_spread(baseline_spread, 1.50),
            "slippage_per_side": slippage_per_side,
        },
        "spread_slippage": {
            "spread": _scaled_spread(baseline_spread, 1.25),
            "slippage_per_side": slippage_per_side * 2,
        },
    }
