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


def test_raw_rd_liquidity_logic_matches_strategy_geometry() -> None:
    for indicator_path in INDICATORS:
        source = indicator_path.read_text(encoding="utf-8")
        scan_start = _function_body(source, "liquidityScanStartBar", "liquidityCandidateIsOwnOrigin")
        demand_scan = _function_body(source, "f_scan_demand_liquidity", "f_scan_supply_liquidity")
        supply_scan = _function_body(source, "f_scan_supply_liquidity", "clearStrategyLiquidityState")
        wrong_side = _function_body(source, "strategyLiquidityWrongSide", "strategyLiquidityGhostData")

        assert "anchorBar - displacementScanBars - formationLegScanBars" in scan_start, (
            f"{indicator_path.name} must start the liquidity scan from the strategy formation/displacement window"
        )
        assert "isValidLocation := pLow < out.bottom" in demand_scan, (
            f"{indicator_path.name} demand liquidity must stay below the zone"
        )
        assert "distFromZone := out.bottom - pLow" in demand_scan, (
            f"{indicator_path.name} demand liquidity distance must be measured from the demand bottom"
        )
        assert "not liquidityCandidateIsOwnOrigin(out, pBar, pLow)" not in demand_scan, (
            f"{indicator_path.name} demand liquidity scan must not add an indicator-only own-origin rejection"
        )
        assert "isValidLocation := pHigh > out.top" in supply_scan, (
            f"{indicator_path.name} supply liquidity must stay above the zone"
        )
        assert "distFromZone := pHigh - out.top" in supply_scan, (
            f"{indicator_path.name} supply liquidity distance must be measured from the supply top"
        )
        assert "not liquidityCandidateIsOwnOrigin(out, pBar, pHigh)" not in supply_scan, (
            f"{indicator_path.name} supply liquidity scan must not add an indicator-only own-origin rejection"
        )
        assert "bool hasStrongLeg = demandLegCount >= minLegCandles" in demand_scan, (
            f"{indicator_path.name} demand liquidity validity must match the strategy leg-count rule"
        )
        assert "bool hasStrongLeg = supplyLegCount >= minLegCandles" in supply_scan, (
            f"{indicator_path.name} supply liquidity validity must match the strategy leg-count rule"
        )
        assert "z.liquidityPrice >= z.bottom" in wrong_side, (
            f"{indicator_path.name} demand wrong-side cleanup must invalidate liquidity inside or above the zone"
        )
        assert "z.liquidityPrice <= z.top" in wrong_side, (
            f"{indicator_path.name} supply wrong-side cleanup must invalidate liquidity inside or below the zone"
        )
