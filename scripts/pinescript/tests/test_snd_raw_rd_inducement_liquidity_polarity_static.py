from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
INDICATORS = [
    ROOT / "scripts/pinescript/indicators/SND_Raw_RD_Forex.pine",
    ROOT / "scripts/pinescript/indicators/SND_Raw_RD_Forex_LAB.pine",
    ROOT / "scripts/pinescript/indicators/SND_Raw_RD_Forex_PROD.pine",
]


def _function_body(source: str, name: str, next_name: str) -> str:
    marker = f"{name}("
    start = source.index(marker)
    next_marker = f"\n{next_name}("
    end = source.index(next_marker, start)
    return source[start:end]


def test_raw_rd_inducement_liquidity_polarity_matches_strategy() -> None:
    for indicator_path in INDICATORS:
        source = indicator_path.read_text(encoding="utf-8")
        demand_scan = _function_body(source, "f_scan_demand_liquidity", "f_scan_supply_liquidity")
        supply_scan = _function_body(source, "f_scan_supply_liquidity", "clearStrategyLiquidityState")
        supply_own_origin = _function_body(source, "supplyOwnOriginLiquidity", "liquidityCompareText")
        wrong_side = _function_body(source, "strategyLiquidityWrongSide", "strategyLiquidityGhostData")

        assert "isValidLocation := pLow >= out.top - (syminfo.mintick * equalLiquidityToleranceTicks)" in demand_scan
        assert "distFromZone := math.max(0.0, pLow - out.top)" in demand_scan
        assert "bool bestLiqBelowTop = false" in supply_scan
        assert "candidateBelowTop := pHigh <= out.top + (syminfo.mintick * equalLiquidityToleranceTicks)" in supply_scan
        assert "distFromZone := candidateBelowTop ? math.max(0.0, out.top - pHigh) : pHigh - out.top" in supply_scan
        assert "bool improvesSide = use_inducement_linking and candidateBelowTop and not bestLiqBelowTop" in supply_scan
        assert "bestLiqBelowTop := candidateBelowTop" in supply_scan
        assert "originHigh <= z.top + tol and originHigh >= z.bottom - tol" in supply_own_origin
        assert "[ownOriginPrice, ownOriginBar, ownOriginDist] = supplyOwnOriginLiquidity(out)" in supply_scan
        assert "not na(ownOriginPrice) and not na(ownOriginBar) and na(bestLiqBar)" in supply_scan
        assert 'bestSource := "OWN_ORIGIN"' in supply_scan
        assert 'bestSource == "OWN_ORIGIN" ? true : supplyLegCount >= minLegCandles' in supply_scan
        assert "candidatePrice <= z.top + tol and candidatePrice >= z.bottom - tol" in source
        assert "use_inducement_linking ? false : z.liquidityPrice < z.top - sideTol" in wrong_side
