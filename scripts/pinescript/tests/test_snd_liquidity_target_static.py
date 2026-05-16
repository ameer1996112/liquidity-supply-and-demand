from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
STRATEGY = ROOT / "scripts/pinescript/strategies/SND_Strategy.pine"


def main() -> None:
    strategy = STRATEGY.read_text(encoding="utf-8")

    public_inputs = [
        'accuracy_zone_mode = input.string("Auto", "Accuracy Zones", options = ["Off", "Auto", "On"], group = GRP_ZONE)',
        'max_zone_age_hours = input.int(7, "Max Zone Age (Hours)", minval = 0, maxval = 72, group = GRP_ZONE)',
        'allow_one_candle_liquidity = input.bool(true, "Allow One-Candle Liquidity", group = GRP_LIQ)',
        'bos_requires_close_beyond = input.bool(false, "Strict BOS: Close Beyond Level", group = GRP_LIQ)',
        'liq_entry_max_dist = input.float(8.7, "Max Zone-to-Liquidity Distance", minval = 0.0, step = 0.1, group = GRP_LIQ)',
    ]

    for needle in public_inputs:
        if needle not in strategy:
            raise AssertionError(f"Missing public premium input: {needle}")

    input_count = strategy.count("input.")
    if input_count != len(public_inputs):
        raise AssertionError(f"Expected only {len(public_inputs)} public inputs, found {input_count}")

    required = [
        'const string GRP_ZONE      = "③ Zone Engine"',
        'const string GRP_LIQ       = "④ Liquidity Proof"',
        "full_wick_symbol = is_gold or is_silver or is_index or is_futures or is_xpt",
        'enable_accuracy_zones = accuracy_zone_mode != "Off"',
        'should_use_accuracy_zones = accuracy_zone_mode == "On" or (accuracy_zone_mode == "Auto" and not full_wick_symbol)',
        "useOneCandleLiquidity = allow_one_candle_liquidity",
        "int minLegCandles = allow_one_candle_liquidity ? 1 : 2",
        "int minCandles = allow_one_candle_liquidity ? 1 : 2",
        "bos_breaks_up(float level) =>",
        "bos_breaks_down(float level) =>",
        "bos_requires_close_beyond ? close > level : high >= level",
        "bos_requires_close_beyond ? close < level : low <= level",
        "zone_is_expired(Core.Zone z) =>",
        "max_zone_age_hours > 0 and not na(z.startTime) and (time - z.startTime) > max_zone_age_hours * 60 * 60 * 1000",
        "not zone_is_expired(_mz_other)",
        "const int MAX_LIQ_SCAN_BARS = 200",
        "const int LIQ_SWEEP_CATCHUP_SCAN_BARS = 200",
        "liq_is_valid_for_demand(float liqLow, float zoneTop) =>",
        "liq_is_valid_for_supply(float liqHigh, float zoneBottom) =>",
        "liq_sweep_tolerance() =>",
        "find_demand_inducement_sweep_bar(int liqBar, float liqPrice) =>",
        "find_supply_inducement_sweep_bar(int liqBar, float liqPrice) =>",
        "scanStartBar = math.max(liqBar + 1, bar_index - LIQ_SWEEP_CATCHUP_SCAN_BARS)",
        "low[off] <= liqPrice + sweepTolerance",
        "high[off] >= liqPrice - sweepTolerance",
        "int maxOff = math.min(bar_index - z.createdBarIndex - 2, MAX_LIQ_SCAN_BARS)",
        "bool isValidLocation = liq_is_valid_for_demand(pLow, z.top)",
        "bool isValidLocation = liq_is_valid_for_supply(pHigh, z.bottom)",
        "for i = offStart to offEnd",
        "z.liquidityValid := hasValidLocation and hasStrongLeg",
        'z.inactiveReason := not hasValidLocation ? "INVALID_LIQUIDITY_INSIDE_ZONE" : (hasStrongLeg ? na : "WAITING_STRONG_LIQUIDITY")',
        "if z.liquiditySwept and not na(z.liqHighPrice)",
        "if z.liquiditySwept and not na(z.liqLowPrice)",
        "bool is_tgt_sweeping_now = bos_breaks_up(z.liqHighPrice)",
        "bool is_tgt_sweeping_now = bos_breaks_down(z.liqLowPrice)",
        "if not checkLiquidityDistance(z, not isDemand)",
        "tp_distance_pips < effective_min_tp_dist",
        "array.set(demandZones, i, z)",
        "array.set(supplyZones, i, z)",
        "if not z.liquidityValid\n                f_scan_demand_liquidity(i)",
        "if not z.liquidityValid\n                f_scan_supply_liquidity(i)",
        "wickIntoZone := currentTouch or prevTouch or z.primed",
        "z.liquidityValid and",
        "z.liquiditySwept and",
        "z.targetSwept and",
        "not z.isHistorical and",
        'string entryComment = "LONG"',
        'string entryComment = "SHORT"',
        'table.cell(zoneInspector, 0, 4, "Liquidity"',
        'table.cell(zoneInspector, 0, 11, "Reason"',
        'working := str.replace_all(working, "D-", "")',
        'working := str.replace_all(working, "S-", "")',
        'str.contains(r, "INVALID_LIQUIDITY_INSIDE_ZONE")',
        'not str.contains(reason, "OVERLAP_VISUALLY_HIDDEN")',
        'z.inactiveReason := "OVERLAP_VISUALLY_HIDDEN"',
        "zone_lab_mode ? labVisible : cleanVisible",
        "z.structureSweepLevel := z.liqHighPrice",
        "z.structureSweepLevel := z.liqLowPrice",
        "z.targetSwept := false",
        "z.liquiditySwept := false",
    ]

    for needle in required:
        if needle not in strategy:
            raise AssertionError(f"Missing accurate liquidity/input contract: {needle}")

    forbidden = [
        "liquidity_candidate_cutoff_bar(Core.Zone z)",
        "external_liquidity_cutoff_bar(Core.Zone z)",
        "pBar < liquidityCutoffBar",
        "int externalCutoffBar = external_liquidity_cutoff_bar(z)",
        "int rangeEnd = math.max(rangeStart, externalCutoffBar - 1)",
        "int effectiveStart = math.max(0, rangeStartAbs)",
        "useOneCandleLiquidity = false",
        "useOneCandleLiquidity ? 1 : 2",
        "bos_break_mode",
        "HOURS_24_MS",
        "time - _mz_other.startTime",
        "str.substring(",
        "bos_requires_close =",
        "targetLevelTouched",
        "targetCloseConfirmed",
        "find_demand_liquidity_own_high",
        "find_supply_liquidity_own_low",
        "LIQ_OWN_LEVEL_LOOKBACK_BARS",
        "revalidate_demand_liquidity_proof",
        "revalidate_supply_liquidity_proof",
        "clear_liquidity_proof",
        'WAITING_LIQ_BOS_LEVEL',
        "hasBosLevel",
        "z.liquidityValid := hasBosLevel and hasStrongLeg",
        "z := revalidate_demand_liquidity_proof(z)",
        "z := revalidate_supply_liquidity_proof(z)",
        "Zone touched before liquidity sweep",
        "z.touchedPreSweep := true",
        "if canEnter and z.touchedPreSweep",
        "Dead Zone: Blocked",
        "Outside RD 5m Session",
        "Outside Trading Hours",
        "Entry candle closed inside zone",
        "mitigated before liquidity sweep",
        "older than 24h",
        "Zone created before min bar index",
        "Existing position open",
        "if not z.liquidityValid or na(z.lastEntryBar)",
        "if z.liquidityValid or na(z.createdBarIndex) or bar_index <= z.createdBarIndex or z.isHistorical",
        "z.liquidityValid and\n     z.liquiditySwept and\n     z.targetSwept and\n     z.causedSweep",
        "if z.liquidityValid and z.liquiditySwept and not na(z.liqHighPrice)",
        "if z.liquidityValid and z.liquiditySwept and not na(z.liqLowPrice)",
        'z.inactiveReason := hasStrongLeg ? na : "WAITING_STRONG_LIQUIDITY"',
        "z.liquidityValid := hasStrongLeg",
        "for i = offEnd to offStart",
        'table.cell(zoneInspector, 0, 4, "Liq Found"',
        'table.cell(zoneInspector, 0, 5, "Strong Leg"',
        'table.cell(zoneInspector, 0, 13, "Reason"',
        "not pf_trading_disabled and not pf_is_news_blackout",
        "liq_entry_max_dist = 0.0",
        "min_tp_distance_pips = 0.0",
        "z.mitigated := true",
        "string demandInvalidReason =",
        "string supplyInvalidReason =",
        "strategy.close_all(comment = pf_daily_kill ?",
        "TOTAL_KILL",
        "string entryComment = (show_entry_labels ?",
        "geomOk := not na(liqLevel) and liqLevel >= (zHigh",
        "geomOk := not na(liqLevel) and liqLevel <= (zLow",
        "LIQ_WRONG_SIDE",
        'group = "📐 Zone Detection"',
        'group = "💧 Liquidity"',
        'group = "🎨 Display"',
        'group = "🎯 Quick Setup"',
        'group = "📊 Trade Execution"',
        'group = "🛡️ Prop Firm / Risk Safety"',
        'group = "⏰ Session & Limits"',
        'z.active and not z.mitigated and na(z.lastEntryBar) and zone_inactive_reason(z) == ""',
        "bool activeDisplayZone = z.active and not z.mitigated",
        "allowedByState := activeDisplayZone",
        "if close_inside_demand or close_below_zone or isTooOld or (invalidate_on_wick and wick_below_zone)\n                    remove_zone_all_arrays(true, i)",
        "if close_inside_supply or close_above_zone or isTooOld or (invalidate_on_wick and wick_above_zone)\n                remove_zone_all_arrays(false, i)",
        "z := clear_liquidity_proof(z, \"LIQ_INSIDE_ZONE\")",
    ]

    for needle in forbidden:
        if needle in strategy:
            raise AssertionError(f"Accurate liquidity/input contract must not use legacy behavior: {needle}")

    print("SND accurate liquidity/input static contract passed")


if __name__ == "__main__":
    main()
