from pathlib import Path


INDICATORS = [
    Path("scripts/pinescript/indicators/SND_Raw_RD_Forex.pine"),
    Path("scripts/pinescript/indicators/SND_Raw_RD_Forex_LAB.pine"),
    Path("scripts/pinescript/indicators/SND_Raw_RD_Forex_PROD.pine"),
]


def _function_body(source: str, name: str, next_name: str) -> str:
    start = source.index(f"{name}(")
    end = source.index(f"\n{next_name}(", start)
    return source[start:end]


def test_demand_liquidity_prefers_non_edge_inducement_candidates() -> None:
    for path in INDICATORS:
        body = _function_body(path.read_text(), "f_scan_demand_liquidity", "f_scan_supply_liquidity")

        assert "bool bestLiqNearEdge = false" in body
        assert "float zoneHeight = math.abs(out.top - out.bottom)" in body
        assert "bool preferAwayFromEdge = use_inducement_linking and zoneHeight >= pip_size * 5.0" in body
        assert "bool isNearEdge = preferAwayFromEdge and distFromZone < pip_size * 2.0" in body
        assert "bool improvesEdgeQuality = bestLiqNearEdge and not isNearEdge" in body
        assert "bool sameEdgeQuality = bestLiqNearEdge == isNearEdge" in body
        assert "if na(bestLiqBar) or improvesEdgeQuality or (sameEdgeQuality and (isCloser or (isSameDistance and isMoreRecent)))" in body
        assert body.count("bestLiqNearEdge := isNearEdge") == 3


def test_supply_liquidity_ranking_remains_reference_strategy_closest_first() -> None:
    for path in INDICATORS:
        body = _function_body(path.read_text(), "f_scan_supply_liquidity", "clearStrategyLiquidityState")

        assert "bestLiqNearEdge" not in body
        assert "preferAwayFromEdge" not in body
