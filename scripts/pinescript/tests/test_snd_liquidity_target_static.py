from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
STRATEGY = ROOT / "scripts/pinescript/strategies/SND_Strategy.pine"


def main() -> None:
    strategy = STRATEGY.read_text(encoding="utf-8")

    required = [
        "useOneCandleLiquidity = true",
        'plotLiq    = input.bool(true, "plotLiq"',
        'show_fractals = input.bool(true, "show_fractals"',
        'show_liquidity_connectors = input.bool(true, "show_liquidity_connectors"',
        "float bestLiqPrice = 1.0e10",
        "float bestLiqPrice = 0.0",
        "int rawMaxOff = bar_index - z.createdBarIndex - 2",
        "int maxOff = math.min(rawMaxOff, MAX_LIQ_SCAN_BARS)",
        "if z.active and not z.mitigated and not z.liquidityValid",
        "if pLow < bestLiqPrice",
        "if pHigh > bestLiqPrice",
        "int rangeEnd = bestLiqBar - 1",
        "z.structureSweepLevel := z.liqHighPrice",
        "z.structureSweepLevel := z.liqLowPrice",
        "bool showLiquidityVisuals = show_liquidity_connectors",
        "const int LIQ_MARK_EXTENSION_BARS = 8",
        "color liq_inducement_pending = color.new(#78716c, 72)",
        "color liq_inducement_swept = color.new(#ea580c, 28)",
        "color liq_target_pending = color.new(#475569, 76)",
        "color liq_target_swept = color.new(#16a34a, 38)",
        "color liq_connector_pending = color.new(#94a3b8, 88)",
        "color liq_connector_swept = color.new(#64748b, 70)",
        "int indLineEnd = z.liquiditySwept and not na(z.liquiditySweptBarIndex) ? math.max(",
        "int tgtLineEnd = z.targetSwept and not na(z.targetSweptBarIndex) ? math.max(",
        "plotshape(show_fractals and not na(fractalHigh), style = shape.triangleup,   location = location.abovebar, color = pvtBtmColor, size = size.tiny",
        "plotshape(show_fractals and not na(fractalLow),  style = shape.triangledown, location = location.belowbar, color = pvtTopColor, size = size.tiny",
        'bool duplicateEligibleReason = reason == "" or str.contains(reason, "WAITING_")',
        "z.active and not z.mitigated ? bar_index + extend_bars : math.max(z.createdBarIndex, rightBar)",
        "bool mitigatedDisplayZone = show_mitigated_zones and z.active and z.mitigated and not invalidOrRejected and not na(z.lastTouchBar)",
        "allowedByState := activeDisplayZone",
        "if is_future_bar and z.leftZone and not z.liquiditySwept and (closes_inside or wicks_into_zone or breaches_zone) and not current_bar_sweeping",
        "if z.active and not z.mitigated",
        "bool demandInvalidated = close_inside_demand or close_below_zone or (invalidate_on_wick and wick_below_zone)",
        "bool supplyInvalidated = close_inside_supply or close_above_zone or (invalidate_on_wick and wick_above_zone)",
        "z.inactiveReason := \"MITIGATED_BY_CLEANUP\"",
    ]

    for needle in required:
        if needle not in strategy:
            raise AssertionError(f"Missing accurate liquidity scan contract: {needle}")

    forbidden = [
        "liquidity_candidate_cutoff_bar(Core.Zone z)",
        "external_liquidity_cutoff_bar(Core.Zone z)",
        "pBar < liquidityCutoffBar",
        "int externalCutoffBar = external_liquidity_cutoff_bar(z)",
        "int rangeEnd = math.max(rangeStart, externalCutoffBar - 1)",
        "int maxOff = bar_index - z.createdBarIndex - 2",
        "if not z.liquidityValid or na(z.lastEntryBar)",
        "useOneCandleLiquidity = false",
        'plotLiq    = input.bool(false, "plotLiq"',
        'show_fractals = input.bool(false, "show_fractals"',
        "bool showLiquidityVisuals = zone_should_show_visual(z, true) and zone_lab_mode and show_liquidity_connectors",
        "bool showLiquidityVisuals = zone_should_show_visual(z, false) and zone_lab_mode and show_liquidity_connectors",
        "color liq_inducement_pending = color.new(#f59e0b, 42)",
        "color liq_inducement_swept = color.new(#f59e0b, 0)",
        "color liq_target_pending = color.new(#38bdf8, 38)",
        "color liq_target_swept = color.new(#22c55e, 0)",
        "color liq_connector_pending = color.new(#94a3b8, 55)",
        "color liq_connector_swept = color.new(#cbd5e1, 18)",
        "color liq_inducement_pending = color.new(#d97706, 76)",
        "color liq_inducement_swept = color.new(#d97706, 38)",
        "color liq_target_pending = color.new(#2563eb, 78)",
        "color liq_target_swept = color.new(#2563eb, 42)",
        "color liq_connector_pending = color.new(#64748b, 84)",
        "color liq_connector_swept = color.new(#64748b, 62)",
        "int lineEnd = bar_index + LIQ_MARK_EXTENSION_BARS",
        "color = color.green, size = size.small",
        "color = color.red,   size = size.small",
        'z.active and not z.mitigated and na(z.lastEntryBar) and zone_inactive_reason(z) == ""',
        "int rightBar = na(z.lastTouchBar) ? bar_index : z.lastTouchBar\n    math.max(z.createdBarIndex, rightBar)",
        "if close_inside_demand or close_below_zone or isTooOld or (invalidate_on_wick and wick_below_zone)\n                    remove_zone_all_arrays(true, i)",
        "if close_inside_supply or close_above_zone or isTooOld or (invalidate_on_wick and wick_above_zone)\n                remove_zone_all_arrays(false, i)",
        "else\n        allowedByState := activeDisplayZone or mitigatedDisplayZone",
    ]

    for needle in forbidden:
        if needle in strategy:
            raise AssertionError(f"Accurate liquidity scan must not use cutoff contract: {needle}")

    print("SND accurate liquidity scan static contract passed")


if __name__ == "__main__":
    main()
