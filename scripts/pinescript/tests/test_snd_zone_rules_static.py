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
        "if proceed_creation\n            float originHigh = baseHigh",
        "\n        int zoneBorderWidth = 1",
    )

    _require(
        strategy,
        [
            'max_displacement_leg_bars = input.int(4, "max_displacement_leg_bars"',
            "findDisplacementBase(bool isDemand, int startOffset, int maxLegBars) =>",
            "int displacementIdx = startOffset + leg - 1",
            "int candidateBaseIdx = startOffset + leg",
            "bool displacementOk = isDemand ? Utils.is_bullish(close[displacementIdx], open[displacementIdx]) : Utils.is_bearish(close[displacementIdx], open[displacementIdx])",
            "bool baseOk = is_valid_zone_base_candle(candidateBaseIdx, isDemand, false)",
            "[baseIdx, legCount]",
            "if createZone(demandBaseIdx, true, false, 1, demandLegCandles, nextZoneId, true)",
            "if createZone(supplyBaseIdx, false, false, 1, supplyLegCandles, nextZoneId, true)",
            "for displacementOffset = 0 to max_scan",
            "if createZone(histDemandBaseIdx, true, true, 1, histDemandLegCandles, nextZoneId, true)",
            "if createZone(histSupplyBaseIdx, false, true, 1, histSupplyLegCandles, nextZoneId, true)",
        ],
        "Displacement left-scan detector",
    )

    _require(
        strategy,
        [
            "is_wide_market_neutral_base(int baseIdx, bool isDemand) =>",
            "bool wideMarket = is_gold or is_xpt or is_index or is_futures",
            "if not wideMarket or baseIdx < 0 or baseIdx > bar_index",
            "bool neutralBody = baseRange > 0 and baseBody <= baseRange * 0.55",
            "bool neutralSideOk = isDemand ? close[baseIdx] <= open[baseIdx] : close[baseIdx] >= open[baseIdx]",
            "is_valid_zone_base_candle(int baseIdx, bool isDemand, bool allowWideMarketNeutral) =>",
            "bool oppositeBase = isDemand ? Utils.is_bearish(close[baseIdx], open[baseIdx]) : Utils.is_bullish(close[baseIdx], open[baseIdx])",
            "oppositeBase or (allowWideMarketNeutral and is_wide_market_neutral_base(baseIdx, isDemand))",
            "bool validBaseSide = is_valid_zone_base_candle(baseIdx, isDemand, true)",
            "bool baseOk = is_valid_zone_base_candle(candidateBaseIdx, isDemand, false)",
        ],
        "Wide-market neutral-base zone detection",
    )

    _require(
        strategy,
        [
            "const int MAX_BAR_INDEX_FUTURE_DRAW = 500",
            "const int MAX_BAR_INDEX_PAST_DRAW = 9999",
            "math.max(bar_index - MAX_BAR_INDEX_PAST_DRAW, math.min(rawRightBar, bar_index + MAX_BAR_INDEX_FUTURE_DRAW))",
        ],
        "Safe bar-index drawing bounds",
    )

    _require(
        strategy,
        [
            "bool proofReady = z.liquidityValid and z.liquiditySwept and z.targetSwept",
            "bool touchesDemand = low <= z.top and high >= z.bottom",
            "bool touchesSupply = high >= z.bottom and low <= z.top",
            "bool closesBelowDemand = close < z.bottom",
            "bool closesAboveSupply = close > z.top",
            "bool wicksBelowDemand = low < z.bottom",
            "bool wicksAboveSupply = high > z.top",
            "bool justLeftZoneThisBar = false",
            "int demandLifecycleSize = array.size(demandZones)",
            "if demandLifecycleSize > 0 and barstate.isconfirmed",
            "for i = 0 to demandLifecycleSize - 1",
            "int supplyLifecycleSize = array.size(supplyZones)",
            "if supplyLifecycleSize > 0 and barstate.isconfirmed",
            "for i = 0 to supplyLifecycleSize - 1",
            "is_future_bar and closesBelowDemand",
            "is_future_bar and closesAboveSupply",
            "is_future_bar and wicksBelowDemand",
            "is_future_bar and wicksAboveSupply",
            "not justLeftZoneThisBar and touchesDemand and not proofReady and not current_bar_sweeping",
            "not justLeftZoneThisBar and touchesSupply and not proofReady and not current_bar_sweeping",
            'z.inactiveReason := "SETUP_INVALID_CLOSE_BELOW_ZONE"',
            'z.inactiveReason := "SETUP_INVALID_CLOSE_ABOVE_ZONE"',
            'z.inactiveReason := "SETUP_INVALID_WICK_BELOW_ZONE"',
            'z.inactiveReason := "SETUP_INVALID_WICK_ABOVE_ZONE"',
            'z.inactiveReason := "SETUP_INVALID_RETURN_BEFORE_PROOF"',
            'invalidateDemandZone(i, "SETUP_INVALID_CLOSE_BELOW_ZONE")',
            'invalidateSupplyZone(i, "SETUP_INVALID_CLOSE_ABOVE_ZONE")',
            'invalidateDemandZone(i, "SETUP_INVALID_WICK_BELOW_ZONE")',
            'invalidateSupplyZone(i, "SETUP_INVALID_WICK_ABOVE_ZONE")',
            'invalidateDemandZone(i, "SETUP_INVALID_RETURN_BEFORE_PROOF")',
            'invalidateSupplyZone(i, "SETUP_INVALID_RETURN_BEFORE_PROOF")',
            "zone_invalidated_after_creation(float zTop, float zBottom, int baseIdx, bool isDemand) =>",
            "bool historicallyInvalid = isHistorical and zone_invalidated_after_creation(zTop, zBottom, baseIdx, isDemand)",
            "if not historicallyInvalid and not skipDuplicateZone",
            "array.set(demandZones, i, z)",
            "array.set(supplyZones, i, z)",
        ],
        "Pre-proof return lifecycle",
    )

    _require(
        strategy,
        [
            "zoneInspector := table.new(position.bottom_right",
            "pf_risk_table = table.new(position.bottom_left",
        ],
        "Zone inspector table position",
    )

    _require(
        strategy,
        [
            "is_base_time_used(baseTime, baseArray) =>",
            "bool alreadyUsed = isDemand ? is_base_time_used(baseTime, used_demand_base_times) : is_base_time_used(baseTime, used_supply_base_times)",
            "array.push(used_demand_base_times, baseTime)",
            "array.push(used_supply_base_times, baseTime)",
            "int nextZoneId = global_zone_id_counter + 1",
            "global_zone_id_counter := nextZoneId",
        ],
        "Deterministic base-time and ID allocation",
    )

    _require(
        boundary_logic,
        [
            "if forceFullWickSymbol\n                    // XAUUSD/indices/futures/XPT: mark the actual normal zone candle.",
            "zTop := baseHigh",
            "zBottom := baseLow",
            "int maxDepartureWickScan = 4",
            "if formation_leg_wick_inclusion and allowDepartureWickExtension",
            "bool demandWickOnlyExtension = legLow < zBottom and math.min(legOpen, legClose) >= zBottom",
            "bool supplyWickOnlyExtension = legHigh > zTop and math.max(legOpen, legClose) <= zTop",
            "if forceFullWickSymbol ? supplyWickOnlyExtension : supplyStandardExtension",
        ],
        "Volatile normal-zone high/low boundaries",
    )
    _require(
        strategy,
        [
            "createZone(int baseIdx, bool isDemand, bool isHistorical, int candlesInBase, int legCandles, int zoneUZID, bool allowDepartureWickExtension) =>",
            "bool forceFullWickSymbol = is_gold or is_silver or is_index or is_futures or is_xpt",
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
            "is_base_bar_used(",
            "global_zone_id_counter := global_zone_id_counter + 1",
            "Utils.is_bullish(close, open) and Utils.is_bullish(close[1], open[1]) and Utils.is_bullish(close[2], open[2]) and Utils.is_bearish(close[3], open[3])",
            "Utils.is_bearish(close, open) and Utils.is_bearish(close[1], open[1]) and Utils.is_bearish(close[2], open[2]) and Utils.is_bullish(close[3], open[3])",
        ],
        "Old hardcoded scanner",
    )

    _require(
        strategy,
        [
            "trades_allowed_today() =>\n    not is_daily_loss_limit_hit() and not is_daily_profit_limit_hit()",
            "if use_half_risk_second_trade and array.get(_current_day_trades, 0) == 1",
        ],
        "Daily risk guard without max-trades cap",
    )

    _forbid(
        strategy,
        [
            "not justLeftZoneThisBar and closesBelowDemand and not proofReady",
            "not justLeftZoneThisBar and closesAboveSupply and not proofReady",
            "not justLeftZoneThisBar and wicksBelowDemand and not proofReady",
            "not justLeftZoneThisBar and wicksAboveSupply and not proofReady",
            "not justLeftZoneThisBar and closesBelowDemand",
            "not justLeftZoneThisBar and closesAboveSupply",
            "not justLeftZoneThisBar and wicksBelowDemand",
            "not justLeftZoneThisBar and wicksAboveSupply",
            "enable_trade_limit",
            "max_trades_per_day",
            "filter_trading_hours",
            "use_rd_5m_session",
            "rd_session_start_hour_utc",
            "rd_session_end_hour_utc",
            "trading_start_hour",
            "trading_end_hour",
            "is_outside_trading_hours()",
            "Outside RD 5m Session",
            "Outside Trading Hours",
            "Session & Limits",
        ],
        "Removed session and daily trade limit settings",
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

    expected_zone_should_show_visual = """zone_should_show_visual(Core.Zone z, bool isDemand) =>
    bool invalidOrRejected = zone_is_invalid_or_rejected(z)
    bool entryUsedArchive = not na(z.lastEntryBar) and not invalidOrRejected
    bool activeDisplayZone = z.active and not z.mitigated and not invalidOrRejected and zone_is_relevant_visual(z, isDemand)
    bool visible = activeDisplayZone or entryUsedArchive
    visible"""

    if _normalize_block(zone_should_show_visual) != _normalize_block(expected_zone_should_show_visual):
        raise AssertionError("Entry-used zone archive display shape changed")

    _require(
        apply_zone_visual,
        [
            "bool entryUsedArchive = not na(z.lastEntryBar) and not invalidOrRejected",
            "if entryUsedArchive",
            "bgColor := isDemand ? col_demand_bg : col_supply_bg",
            "borderColor := isDemand ? col_demand_border : col_supply_border",
            "color labelColor = invalidOrRejected or (usedOrMitigated and not entryUsedArchive) ? col_used_zone_border",
        ],
        "Entry-used zones keep side color",
    )

    _forbid(
        zone_should_show_visual,
        [
            "show_entry_used_zones",
            "zone_lab_mode",
            "show_mitigated_zones",
            "show_invalid_zones",
            "show_candidate_zones",
        ],
        "Removed visual mode logic",
    )

    print("SND displacement scanner static contract passed")


if __name__ == "__main__":
    main()
