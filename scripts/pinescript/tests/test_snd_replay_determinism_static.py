from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
STRATEGY = ROOT / "scripts/pinescript/strategies/SND_Strategy.pine"


def _function_body(source: str, name: str) -> str:
    start = source.index(f"{name}(")
    end = source.index("\nremove_zone_all_arrays(", start)
    return source[start:end]


def main() -> None:
    strategy = STRATEGY.read_text(encoding="utf-8")

    required = [
        'replay_live_mode = input.bool(true, "Replay Live Mode", group="⑦ Advanced / Debug")',
        'replay_rescan_bars = input.int(5, "Replay Recent Rescan Bars", minval=0, maxval=10, group="⑦ Advanced / Debug")',
        "is_base_time_used(baseTime, used_demand_base_times)",
        "is_base_time_used(baseTime, used_supply_base_times)",
        "if barstate.isconfirmed and not initial_scan_done and not replay_live_mode and bar_index > 50",
        "int demandCountNow = array.size(demandZones)",
        "int supplyCountNow = array.size(supplyZones)",
        "scanRecentReplayZones()",
        "bool created = false",
        "created := true",
        "nextCounter += 1",
        "bool should_rescan_demand_liq = not z.liquidityValid or (legacy_liquidity_live_update and na(z.lastEntryBar) and not z.targetSwept)",
        "bool should_rescan_supply_liq = not z.liquidityValid or (legacy_liquidity_live_update and na(z.lastEntryBar) and not z.targetSwept)",
        "var array<int> replay_rescan_demand_base_times = array.new_int()",
        "var array<int> replay_rescan_supply_base_times = array.new_int()",
        "mark_replay_rescan_attempt(baseTime, isDemand)",
        "bool rememberReplayAttempt = replayOffset > 0",
        "rememberReplayAttempt and is_replay_rescan_attempted(baseTime, isDemand)",
        "int replayScanOffset = replayScanCount",
        "while replayScanOffset >= 0",
        "replayScanOffset -= 1",
        "resolve_first_base_idx(int candidateBaseIdx, bool isDemand) =>",
        "int resolvedBaseIdx = resolve_first_base_idx(baseIdx, isDemand)",
        "bool olderMoreDistal = isDemand ? low[olderIdx] <= low[firstBaseIdx] + syminfo.mintick : high[olderIdx] >= high[firstBaseIdx] - syminfo.mintick",
        "if sameSideBase and olderMoreDistal",
        "int baseTime = time[resolvedBaseIdx]",
        "if createZone(resolvedBaseIdx, isDemand, isHistorical, 1, legCandles, nextCounter + 1)",
    ]

    for needle in required:
        if needle not in strategy:
            raise AssertionError(f"Missing replay determinism contract: {needle}")

    forbidden = [
        "cached_demand_size",
        "cached_supply_size",
        "is_base_bar_used(baseBarIdx",
        "is_base_bar_used(baseBarIdxDemand",
        "is_base_bar_used(baseBarIdxSupply",
    ]

    for needle in forbidden:
        if needle in strategy:
            raise AssertionError(f"Replay determinism contract forbids stale behavior: {needle}")

    create_zone = _function_body(strategy, "createZone")

    demand_push = create_zone.index("array.unshift(demandZones, z)")
    demand_db = create_zone.index('db_upsertZone(z, "DEMAND")')
    demand_used = create_zone.index("array.push(used_demand_base_times, baseTime)")
    if not (demand_push < demand_db < demand_used):
        raise AssertionError("Demand baseTime must be marked used only after push and db_upsertZone")

    supply_push = create_zone.index("array.unshift(supplyZones, z)")
    supply_db = create_zone.index('db_upsertZone(z, "SUPPLY")')
    supply_used = create_zone.index("array.push(used_supply_base_times, baseTime)")
    if not (supply_push < supply_db < supply_used):
        raise AssertionError("Supply baseTime must be marked used only after push and db_upsertZone")

    created_true = create_zone.index("created := true")
    created_return = create_zone.rindex("created")
    if not (demand_used < created_true and supply_used < created_true and created_true < created_return):
        raise AssertionError("createZone must return true only after a zone is pushed and marked used")

    maybe_create = strategy[strategy.index("maybeCreateDetectedZone(") : strategy.index("\nremove_zone_all_arrays(", strategy.index("maybeCreateDetectedZone("))]
    if "nextCounter += 1\n        createZone" in maybe_create:
        raise AssertionError("Zone counter must not increment before createZone confirms creation")
    if "if createZone(resolvedBaseIdx, isDemand, isHistorical, 1, legCandles, nextCounter + 1)" not in maybe_create:
        raise AssertionError("maybeCreateDetectedZone must call createZone with the resolved first base before incrementing the counter")
    if "rememberReplayAttempt and is_replay_rescan_attempted(baseTime, isDemand)" not in maybe_create:
        raise AssertionError("Replay rescans must skip base times already retried")

    replay_scan = strategy[strategy.index("scanRecentReplayZones()") : strategy.index("\n\nif barstate.isconfirmed and bar_index > 10")]
    if "for replayScanOffset = 0 to replayScanCount" in replay_scan:
        raise AssertionError("Replay rescan must process oldest-to-newest, not current-to-oldest")
    if replay_scan.index("int replayScanOffset = replayScanCount") > replay_scan.index("while replayScanOffset >= 0"):
        raise AssertionError("Replay rescan must initialize from the oldest offset before the loop")

    scan_patterns = strategy[strategy.index("scanZonePatternsAtOffset(") : strategy.index("\nscanRecentReplayZones()")]
    first_demand_pattern = scan_patterns.index("Utils.is_bullish(close[replayOffset], open[replayOffset])")
    demand_continuation = scan_patterns.index("for demandContBaseOffset = 1 to formation_leg_scan_bars")
    if demand_continuation > first_demand_pattern:
        raise AssertionError("Gold demand continuation candidates must be tried before standard demand bases")
    first_supply_pattern = scan_patterns.index("Utils.is_bearish(close[replayOffset], open[replayOffset])")
    supply_continuation = scan_patterns.index("for supplyContBaseOffset = 1 to formation_leg_scan_bars")
    if supply_continuation > first_supply_pattern:
        raise AssertionError("Gold supply continuation candidates must be tried before standard supply bases")

    print("SND replay determinism static contract passed")


if __name__ == "__main__":
    main()
