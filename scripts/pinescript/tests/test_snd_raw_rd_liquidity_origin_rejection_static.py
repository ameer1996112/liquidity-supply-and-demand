from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
INDICATORS = [
    ROOT / "scripts/pinescript/indicators/SND_Raw_RD_Forex.pine",
    ROOT / "scripts/pinescript/indicators/SND_Raw_RD_Forex_LAB.pine",
    ROOT / "scripts/pinescript/indicators/SND_Raw_RD_Forex_PROD.pine",
]


def _function_body(source: str, name: str, next_name: str) -> str:
    marker = f"{name}("
    if marker not in source:
        return ""
    start = source.index(marker)
    next_marker = f"\n{next_name}("
    if next_marker not in source[start:]:
        return source[start:]
    end = source.index(next_marker, start)
    return source[start:end]


def test_liquidity_scans_allow_zone_origin_candidates_like_strategy() -> None:
    for indicator_path in INDICATORS:
        source = indicator_path.read_text(encoding="utf-8")
        demand_scan = _function_body(source, "f_scan_demand_liquidity", "f_scan_supply_liquidity")
        supply_scan = _function_body(source, "f_scan_supply_liquidity", "clearStrategyLiquidityState")

        assert "not liquidityCandidateIsOwnOrigin(out, pBar, pLow)" not in demand_scan, (
            f"{indicator_path.name} demand liquidity scan must allow own-origin edge liquidity like SND_Strategy"
        )
        assert "not liquidityCandidateIsOwnOrigin(out, pBar, pHigh)" not in supply_scan, (
            f"{indicator_path.name} supply liquidity scan must allow own-origin edge liquidity like SND_Strategy"
        )
