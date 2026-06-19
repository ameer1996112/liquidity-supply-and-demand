from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
INDICATORS = [
    ROOT / "scripts/pinescript/indicators/SND_Raw_RD_Forex.pine",
    ROOT / "scripts/pinescript/indicators/SND_Raw_RD_Forex_LAB.pine",
    ROOT / "scripts/pinescript/indicators/SND_Raw_RD_Forex_PROD.pine",
]


def _body(source: str, start_marker: str, end_marker: str) -> str:
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[start:end]


def test_raw_rd_selects_closest_liquidity_per_zone() -> None:
    for indicator_path in INDICATORS:
        source = indicator_path.read_text(encoding="utf-8")
        demand_scan = _body(source, "f_scan_demand_liquidity", "\nf_scan_supply_liquidity")
        supply_scan = _body(source, "f_scan_supply_liquidity", "\nclearStrategyLiquidityState")

        assert "bool isCloser = distFromZone < bestDist" in demand_scan
        assert "bool isSameDistance = distFromZone == bestDist" in demand_scan
        assert "bool isMoreRecent = na(bestLiqBar) or pBar > bestLiqBar" in demand_scan
        assert "if na(bestLiqBar) or isCloser or (isSameDistance and isMoreRecent)" in demand_scan, (
            f"{indicator_path.name} demand liquidity must choose the closest valid line to the zone"
        )

        for forbidden in [
            "bestLiqNearEdge",
            "preferAwayFromEdge",
            "isNearEdge",
            "improvesEdgeQuality",
            "sameEdgeQuality",
        ]:
            assert forbidden not in demand_scan, (
                f"{indicator_path.name} demand liquidity must not override closest-line selection with edge-quality bias: {forbidden}"
            )

        assert "bool isCloser = distFromZoneCheck < bestDist" in supply_scan
        assert "bool isSameDistance = distFromZoneCheck == bestDist" in supply_scan
        assert "bool isMoreRecent = na(bestLiqBar) or pBar > bestLiqBar" in supply_scan
