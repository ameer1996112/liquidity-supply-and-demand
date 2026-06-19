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


def test_liquidity_rescan_happens_after_cleanup() -> None:
    for indicator_path in INDICATORS:
        source = indicator_path.read_text(encoding="utf-8")
        link_body = _function_body(source, "linkLiquidityAndTargets", "processZone")

        wrong_side_idx = link_body.index("if strategyLiquidityWrongSide(out)")
        ghost_idx = link_body.index("if strategyLiquidityGhostData(out)")
        demand_scan_idx = link_body.index("f_scan_demand_liquidity(out)")
        supply_scan_idx = link_body.index("f_scan_supply_liquidity(out)")

        assert demand_scan_idx > ghost_idx, (
            f"{indicator_path.name} must compute the demand liquidity rescan from the post-cleanup zone state"
        )
        assert supply_scan_idx > ghost_idx, (
            f"{indicator_path.name} must compute the supply liquidity rescan from the post-cleanup zone state"
        )
        assert "RawZone demandScan = f_scan_demand_liquidity(out)" in link_body
        assert "RawZone supplyScan = f_scan_supply_liquidity(out)" in link_body
