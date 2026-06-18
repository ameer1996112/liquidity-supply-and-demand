from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
STRATEGY = ROOT / "scripts/pinescript/strategies/SND_Strategy.pine"


def _body(source: str, start_marker: str, end_marker: str) -> str:
    if start_marker not in source:
        return ""
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[start:end]


def _require(source: str, needles: list[str], label: str) -> None:
    missing = [needle for needle in needles if needle not in source]
    if missing:
        raise AssertionError(f"{label} missing:\n" + "\n".join(missing))


def _forbid(source: str, needles: list[str], label: str) -> None:
    present = [needle for needle in needles if needle in source]
    if present:
        raise AssertionError(f"{label} must not contain:\n" + "\n".join(present))


def _normalize_block(source: str) -> str:
    return "\n".join(line.rstrip() for line in source.strip().splitlines())


def main() -> None:
    strategy = STRATEGY.read_text(encoding="utf-8")
    display_settings = _body(
        strategy,
        "show_zones           = true",
        "trade_direction       = input.string(",
    )
    zone_should_show_visual = _body(
        strategy,
        "zone_should_show_visual(Core.Zone z, bool isDemand) =>",
        "apply_zone_visual(Core.Zone z, bool isDemand) =>",
    )
    apply_zone_visual = _body(
        strategy,
        "apply_zone_visual(Core.Zone z, bool isDemand) =>",
        "zone_overlap_pct(float topA, float bottomA, float topB, float bottomB) =>",
    )
    boundary_logic = _body(
        strategy,
        "float clusterBodyHigh = math.max(baseOpen, baseClose)",
        "\n        float base_width = clusterHigh - clusterLow",
    )

    _require(
        strategy,
        [
            "findDisplacementBase(bool isDemand, int startOffset, int maxLegBars) =>",
            "int baseIdx = na",
            "int legCount = 0",
            "int rejectIdx = na",
            'string rejectReason = ""',
            "for scan = 1 to maxLegBars",
            "int candidateBaseIdx = startOffset + scan",
            "bool baseOk = isDemand ? Utils.is_bearish(close[candidateBaseIdx], open[candidateBaseIdx]) : Utils.is_bullish(close[candidateBaseIdx], open[candidateBaseIdx])",
            "bool directionalCandle = isDemand ? Utils.is_bullish(close[legOffset], open[legOffset]) : Utils.is_bearish(close[legOffset], open[legOffset])",
            "if displacement_leg_confirmed(legOffset, candidateBaseIdx, isDemand)",
            "else if formation_leg_retouches_zone_after_leave(candidateBaseIdx, isDemand, startOffset)",
            "if not na(demandBaseIdx) and not is_base_time_used(demandBaseIdx, used_demand_base_times)",
            "createZone(demandBaseIdx, true, false, 1, demandLegCandles, global_zone_id_counter)",
            "createZone(supplyBaseIdx, false, false, 1, supplyLegCandles, global_zone_id_counter)",
            "for contBaseIdx = 1 to formation_leg_scan_bars",
            "createZone(contBaseIdx, true, false, 1, 1, global_zone_id_counter, true)",
            "createZone(contBaseIdx, false, false, 1, 1, global_zone_id_counter, true)",
            "for displacementIdx = 0 to max_displacement_scan",
            "createZone(demandBaseIdx, true, true, 1, demandLegCandles, global_zone_id_counter)",
            "createZone(supplyBaseIdx, false, true, 1, supplyLegCandles, global_zone_id_counter)",
        ],
        "Displacement left-scan detector",
    )

    _require(
        strategy,
        [
            "is_gold_continuation_zone(int baseIdx, bool isDemand) =>",
            "bool enabled = gold_continuation_zones",
            "bool compactBase = baseRange > syminfo.mintick and baseRange <= atr14 * 1.8 and baseBody <= baseRange * 0.65",
            "bool validBaseSide = isDemand ? close[baseIdx] < open[baseIdx] : close[baseIdx] > open[baseIdx]",
            "bool continuationApproach = isDemand ? close[baseIdx + 1] > open[baseIdx + 1] : close[baseIdx + 1] < open[baseIdx + 1]",
            "bool reversalApproach = isDemand ? close[baseIdx + 1] < open[baseIdx + 1] : close[baseIdx + 1] > open[baseIdx + 1]",
            "bool confirmsAway = false",
            "bool shallowPullback = isDemand ? low[baseIdx] >= priorBodyEdge - atr14 * 0.25 : high[baseIdx] <= priorBodyEdge + atr14 * 0.25",
            "bool reversalExtreme = isDemand ? low[baseIdx] <= low[baseIdx + 1] + atr14 * 0.25 : high[baseIdx] >= high[baseIdx + 1] - atr14 * 0.25",
            "bool validApproach = (continuationApproach and shallowPullback) or (reversalApproach and reversalExtreme)",
            "result := compactBase and validBaseSide and validApproach and confirmsAway",
        ],
        "Gold continuation zone detection",
    )

    _require(
        strategy,
        [
            "zone_visual_right(Core.Zone z) =>",
            "int stopBar = visual_stop_bar(z.id)",
            "not na(stopBar) ? stopBar : bar_index",
            "int right_bar_index = zone_visual_right(z)",
        ],
        "Safe bar-index drawing bounds",
    )

    _require(
        strategy,
        [
            "int demandSize = array.size(demandZones)",
            "if demandSize > 0",
            "for i = demandSize - 1 to 0",
            "bool close_below_zone = current_close < z.bottom",
            "bool wick_below_zone  = current_low < z.bottom",
            "bool close_inside_zone = current_close <= z.top and current_close >= z.bottom",
            "bool wick_mitigates_zone = z.isHistorical and z.leftZone and not z.mitigated and current_low <= z.top and current_high >= z.bottom",
            "bool visual_zone_touch = not na(visualLeaveBar) and bar_index > visualLeaveBar and current_low <= z.top and current_high >= z.bottom",
            "bool touch_sweep_now = z.liqSource == TOUCH_SWEEP_SOURCE and z.liquiditySwept and z.liquiditySweptBarIndex == bar_index",
            "bool returned_invalid_after_left = not touch_sweep_now and zone_failed_after_leave(z, true)",
            "bool returned_before_liq_sweep = require_liquidity_sweep and not touch_sweep_now and z.leftZone and (current_low <= z.top or z.mitigated) and (not z.liquidityValid or not z.liquiditySwept or na(z.liquiditySweptBarIndex) or bar_index <= z.liquiditySweptBarIndex)",
            "int confirmationBar = not na(z.departureEndBarIndex) ? z.departureEndBarIndex : z.createdBarIndex",
            "int invalidationStartBar = not na(z.firstInvalidBarIndex) ? z.firstInvalidBarIndex : confirmationBar + 1",
            "bool afterConfirmation = bar_index >= invalidationStartBar",
            "bool departedAfterConfirmation = not na(z.structureBreakBarIndex) and z.structureBreakBarIndex >= invalidationStartBar",
            "bool canJudgeInvalidation = afterConfirmation and departedAfterConfirmation",
            "bool validSweepOrProof = z.liquidityValid and z.liquiditySwept",
            "bool gatedReturnedBeforeLiqSweep = canJudgeInvalidation and not validSweepOrProof and returned_before_liq_sweep",
            "bool gatedReturnedInvalidAfterLeft = canJudgeInvalidation and not validSweepOrProof and returned_invalid_after_left",
            "bool gatedCloseBelowZone = canJudgeInvalidation and not validSweepOrProof and close_below_zone",
            "bool gatedWickBelowZone = canJudgeInvalidation and not validSweepOrProof and invalidate_on_wick and wick_below_zone",
            "if gatedReturnedBeforeLiqSweep or gatedReturnedInvalidAfterLeft or gatedCloseBelowZone or gatedWickBelowZone or isTooOld",
            "remove_zone_all_arrays(true, i)",
            "int supplySize = array.size(supplyZones)",
            "if supplySize > 0",
            "for i = supplySize - 1 to 0",
            "bool close_above_zone = current_close > z.top",
            "bool wick_above_zone  = current_high > z.top",
            "bool wick_mitigates_zone = z.isHistorical and z.leftZone and not z.mitigated and current_high >= z.bottom and current_low <= z.top",
            "bool visual_zone_touch = not na(visualLeaveBar) and bar_index > visualLeaveBar and current_high >= z.bottom and current_low <= z.top",
            "bool touch_sweep_now = z.liqSource == TOUCH_SWEEP_SOURCE and z.liquiditySwept and z.liquiditySweptBarIndex == bar_index",
            "bool returned_invalid_after_left = not touch_sweep_now and zone_failed_after_leave(z, false)",
            "bool returned_before_liq_sweep = require_liquidity_sweep and not touch_sweep_now and z.leftZone and (current_high >= z.bottom or z.mitigated) and (not z.liquidityValid or not z.liquiditySwept or na(z.liquiditySweptBarIndex) or bar_index <= z.liquiditySweptBarIndex)",
            "bool departedAfterConfirmation = not na(z.structureBreakBarIndex) and z.structureBreakBarIndex >= invalidationStartBar",
            "bool canJudgeInvalidation = afterConfirmation and departedAfterConfirmation",
            "bool validSweepOrProof = z.liquidityValid and z.liquiditySwept",
            "bool gatedReturnedBeforeLiqSweep = canJudgeInvalidation and not validSweepOrProof and returned_before_liq_sweep",
            "bool gatedReturnedInvalidAfterLeft = canJudgeInvalidation and not validSweepOrProof and returned_invalid_after_left",
            "bool gatedCloseAboveZone = canJudgeInvalidation and not validSweepOrProof and close_above_zone",
            "bool gatedWickAboveZone = canJudgeInvalidation and not validSweepOrProof and invalidate_on_wick and wick_above_zone",
            "if gatedReturnedBeforeLiqSweep or gatedReturnedInvalidAfterLeft or gatedCloseAboveZone or gatedWickAboveZone or isTooOld",
            "remove_zone_all_arrays(false, i)",
        ],
        "Pre-proof return lifecycle",
    )

    _require(
        strategy,
        [
            "zoneInspector := table.new(position.bottom_right",
            "profileStatusTable := table.new(position.bottom_center",
        ],
        "Zone inspector table position",
    )

    _require(
        strategy,
        [
            "is_base_time_used(int baseIdx, array<int> baseArray) =>",
            "baseIdx >= 0 and baseIdx <= bar_index and array.includes(baseArray, time[baseIdx])",
            "array.push(used_demand_base_times, baseTime)",
            "array.push(used_supply_base_times, baseTime)",
            "array.includes(used_demand_base_times, baseTime)",
            "array.includes(used_supply_base_times, baseTime)",
            "global_zone_id_counter := global_zone_id_counter + 1",
        ],
        "Deterministic base-time and ID allocation",
    )

    _require(
        boundary_logic,
        [
            "float clusterBodyHigh = math.max(baseOpen, baseClose)",
            "float clusterBodyLow  = math.min(baseOpen, baseClose)",
            "float clusterWickHigh = baseHigh",
            "float clusterWickLow  = baseLow",
            "float clusterHigh = baseHigh",
            "float clusterLow  = baseLow",
            "int   actualCandlesInBase = 1",
            "int   max_base_lookback = 15",
            "float atr_cap = (is_index or is_gold or is_xpt) ? atr14 * 1.5 : atr14",
            "float body_threshold = (is_index or is_gold or is_xpt) ? 0.85 : 0.50",
            "float adj_tolerance = (is_index or is_gold or is_xpt) ? atr14 * 0.25 : 0.0",
            "actualCandlesInBase += 1",
        ],
        "Volatile normal-zone high/low boundaries",
    )
    _require(
        strategy,
        [
            "createZone(int baseIdx, bool isDemand, bool isHistorical, int candlesInBase, int legCandles, int zoneUZID, bool allowUsedBase = false) =>",
            "int baseTime = time[baseIdx]",
            "bool alreadyUsed = false",
            "if isDemand",
            "if array.includes(used_demand_base_times, baseTime)",
            "if array.includes(used_supply_base_times, baseTime)",
        ],
        "Volatile symbol detection",
    )

    _forbid(
        boundary_logic,
        [
            "zTop := clusterHigh",
            "zBottom := clusterLow",
            "XAUUSD/indices/futures: keep the whole relevant base cluster.",
            "if not forceFullWickSymbol\n                int maxDepartureWickScan = 4",
            "if formation_leg_wick_inclusion and not forceFullWickSymbol",
            "if formation_leg_wick_inclusion\n",
        ],
        "Volatile normal-zone cluster widening",
    )

    _forbid(
        strategy,
        [
            "Utils.is_bullish(close, open) and Utils.is_bullish(close[1], open[1]) and Utils.is_bullish(close[2], open[2]) and Utils.is_bearish(close[3], open[3])",
            "Utils.is_bearish(close, open) and Utils.is_bearish(close[1], open[1]) and Utils.is_bearish(close[2], open[2]) and Utils.is_bullish(close[3], open[3])",
        ],
        "Old hardcoded scanner",
    )

    _require(
        strategy,
        [
            "trades_allowed_today() =>\n    trade_limit_ok = enable_trade_limit ? array.get(_current_day_trades, 0) < max_trades_per_day : true",
            "if use_half_risk_second_trade and array.get(_current_day_trades, 0) == 1 and max_trades_per_day == 2",
            "filter_trading_hours = input.bool(true, \"Trading Hours Only\"",
            "trading_start_hour = input.int(7, \"   └─ Start Hour (UTC)\"",
            "trading_end_hour = input.int(22, \"   └─ End Hour (UTC)\"",
            "profileStatusTable := table.new(position.bottom_center",
        ],
        "Current session and daily trade limit settings",
    )

    _forbid(
        display_settings,
        [
            "zone_lab_mode",
            "show_invalid_zones",
            "show_mitigated_zones",
            "show_candidate_zones",
            "show_rejection_reason_labels",
            "show_entry_used_zones",
        ],
        "Removed visual mode inputs",
    )

    _require(
        _body(strategy, "clear_visual_lifecycle(int zoneId) =>", "zone_visual_right(Core.Zone z) =>"),
        [
            "clear_visual_stop(zoneId)",
            "clear_visual_leave(zoneId)",
            "true",
        ],
        "Visual lifecycle cleanup",
    )

    _require(
        strategy,
        [
            "zone_visual_right(Core.Zone z) =>",
            "int stopBar = visual_stop_bar(z.id)",
            "not na(stopBar) ? stopBar : bar_index",
        ],
        "Entry-used zone archive display shape",
    )

    print("SND displacement scanner static contract passed")


if __name__ == "__main__":
    main()
