from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
STRATEGY = ROOT / "scripts/pinescript/strategies/SND_Strategy.pine"


def _body(source: str, start_marker: str, end_marker: str) -> str:
    if start_marker not in source:
        return ""
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[start:end]


def main() -> None:
    strategy = STRATEGY.read_text(encoding="utf-8")
    demand_sweeps = _body(strategy, "f_check_demand_sweeps", "\nf_check_supply_sweeps")
    supply_sweeps = _body(strategy, "f_check_supply_sweeps", "\n\ntrimBaseTimeArrays")
    demand_scan = _body(strategy, "f_scan_demand_liquidity", "\nf_scan_supply_liquidity")
    supply_scan = _body(strategy, "f_scan_supply_liquidity", "\nf_check_demand_sweeps")

    required = [
        "bos_breaks_up(float level) =>",
        "bos_breaks_down(float level) =>",
        "bos_requires_close_beyond ? close > level : high >= level",
        "bos_requires_close_beyond ? close < level : low <= level",
        "zone_proof_ready(Core.Zone z) =>",
        "z.liquidityValid and z.liquiditySwept and z.targetSwept",
        "z.structureSweepLevel := z.liqHighPrice",
        "z.structureSweepLevel := z.liqLowPrice",
        "z.targetSwept := false",
        "z.liquiditySwept := false",
        "z.targetSweptBarIndex := na",
        "z.liquiditySweptBarIndex := na",
    ]

    for needle in required:
        if needle not in strategy:
            raise AssertionError(f"Missing liquidity target contract marker: {needle}")

    demand_required = [
        "if z.liquidityValid and z.liquiditySwept and not na(z.liqHighPrice) and not na(z.liqHighBar) and not z.targetSwept",
        "bool is_tgt_sweeping_now = bos_breaks_up(z.liqHighPrice)",
        "z.targetSwept := true",
        "z.targetSweptBarIndex := bar_index",
    ]

    for needle in demand_required:
        if needle not in demand_sweeps:
            raise AssertionError(f"Demand target/BOS rule missing: {needle}")

    supply_required = [
        "if z.liquidityValid and z.liquiditySwept and not na(z.liqLowPrice) and not na(z.liqLowBar) and not z.targetSwept",
        "bool is_tgt_sweeping_now = bos_breaks_down(z.liqLowPrice)",
        "z.targetSwept := true",
        "z.targetSweptBarIndex := bar_index",
    ]

    for needle in supply_required:
        if needle not in supply_sweeps:
            raise AssertionError(f"Supply target/BOS rule missing: {needle}")

    scan_required = [
        "int rangeEnd = bestLiqBar - 1",
        "bestTargetBar := getBarOfMaxHigh(rangeStart, rangeEnd)",
        "bestTargetBar := getBarOfMinLow(rangeStart, rangeEnd)",
        "int maxOff = math.min(rawMaxOff, MAX_LIQ_SCAN_BARS)",
    ]

    for needle in scan_required:
        if needle not in demand_scan and needle not in supply_scan:
            raise AssertionError(f"Liquidity scan target rule missing: {needle}")

    forbidden = [
        "targetLevelTouched",
        "targetCloseConfirmed",
        "WAITING_LIQ_BOS_LEVEL",
        "hasBosLevel",
        "z.liquidityValid := hasBosLevel and hasStrongLeg",
        "LIQ_WRONG_SIDE",
        "if z.liquidityValid and not na(z.liqHighPrice) and not na(z.liqHighBar) and not z.targetSwept",
        "if z.liquidityValid and not na(z.liqLowPrice) and not na(z.liqLowBar) and not z.targetSwept",
    ]

    for needle in forbidden:
        if needle in strategy:
            raise AssertionError(f"Forbidden stale liquidity target behavior: {needle}")

    print("SND liquidity target static contract passed")


if __name__ == "__main__":
    main()
