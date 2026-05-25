#!/usr/bin/env python3
"""Static checks for leg-based zone candidate creation."""

from pathlib import Path


STRATEGY = Path(__file__).resolve().parents[1] / "strategies" / "SND_Strategy.pine"


def main() -> None:
    source = STRATEGY.read_text()

    required_markers = [
        'displacement_base_scan_bars = input.int(6, "displacement_base_scan_bars"',
        'is_base_time_used(int baseIdx, array<int> baseArray) =>',
        'displacement_leg_confirmed(int displacementIdx, int baseIdx, bool isDemand) =>',
        'is_reclaim_wick_base_candle(int baseIdx, bool isDemand) =>',
        'bool wickBeyondDeparture = baseIdx - 1 >= 0 and (isDemand ? low[baseIdx] < low[baseIdx - 1] : high[baseIdx] > high[baseIdx - 1])',
        'bool enabled = gold_continuation_zones',
        'findDisplacementBase(bool isDemand, int startOffset, int maxLegBars) =>',
        '[demandBaseIdx, demandLegCandles] = findDisplacementBase(true, 0, displacement_base_scan_bars)',
        '[supplyBaseIdx, supplyLegCandles] = findDisplacementBase(false, 0, displacement_base_scan_bars)',
        'max_displacement_scan = math.min(300, bar_index)',
        '[demandBaseIdx, demandLegCandles] = findDisplacementBase(true, displacementIdx, displacement_base_scan_bars)',
        '[supplyBaseIdx, supplyLegCandles] = findDisplacementBase(false, displacementIdx, displacement_base_scan_bars)',
        'bool created = false',
        'created := true',
        'createZone(',
    ]

    missing = [marker for marker in required_markers if marker not in source]
    if missing:
        raise AssertionError("Missing independent zone candidate creation markers:\n" + "\n".join(missing))

    forbidden_markers = [
        "else if demandPattern2",
        "else if demandPattern1",
        "else if supplyPattern2",
        "else if supplyPattern1",
        "else if historicalDemandPattern2",
        "else if historicalDemandPattern1",
        "else if historicalSupplyPattern2",
        "else if historicalSupplyPattern1",
        "bool demandPattern3",
        "bool demandPattern2",
        "bool demandPattern1",
        "bool supplyPattern3",
        "bool supplyPattern2",
        "bool supplyPattern1",
        "bool historicalDemandPattern3",
        "bool historicalDemandPattern2",
        "bool historicalDemandPattern1",
        "bool historicalSupplyPattern3",
        "bool historicalSupplyPattern2",
        "bool historicalSupplyPattern1",
        "float bestBasePrice = na",
        "float candidatePrice = isDemand ? low[candidateIdx] : high[candidateIdx]",
        "bool betterBase = na(foundBaseIdx) or (isDemand ? candidatePrice < bestBasePrice : candidatePrice > bestBasePrice)",
        "bool neutralBase = baseRange > syminfo.mintick and baseBody <= baseRange * 0.50",
        "bool oppositeBase = isDemand ? Utils.is_bearish(close[idx], open[idx]) : Utils.is_bullish(close[idx], open[idx])",
        "bool supportedNeutralBase = false",
        "for supportScan = 1 to 2",
        "bool supportOpposite = isDemand ? Utils.is_bearish(close[supportIdx], open[supportIdx]) : Utils.is_bullish(close[supportIdx], open[supportIdx])",
        "oppositeBase or supportedNeutralBase",
        "bool enabled = gold_continuation_zones and (is_gold or is_xpt)",
        "is_displacement_candle(int idx, bool isDemand) =>",
        "is_displacement_base_candle(int idx, bool isDemand) =>",
        "find_displacement_base_idx(int displacementIdx, bool isDemand) =>",
        "else if Utils.is_bullish(close, open) and Utils.is_bullish(close[1], open[1]) and Utils.is_bearish(close[2], open[2])",
        "else if Utils.is_bullish(close, open) and Utils.is_bearish(close[1], open[1])",
        "else if Utils.is_bearish(close, open) and Utils.is_bearish(close[1], open[1]) and Utils.is_bullish(close[2], open[2])",
        "else if Utils.is_bearish(close, open) and Utils.is_bullish(close[1], open[1])",
        "else if Utils.is_bearish(close[i], open[i]) and Utils.is_bullish(close[i - 1], open[i - 1])",
        "else if Utils.is_bullish(close[i], open[i]) and Utils.is_bearish(close[i - 1], open[i - 1])",
    ]
    present_forbidden = [marker for marker in forbidden_markers if marker in source]
    if present_forbidden:
        raise AssertionError("Found mutually exclusive zone candidate markers:\n" + "\n".join(present_forbidden))

    demand_push = source.find("array.push(used_demand_base_times, baseTime)")
    demand_upsert = source.find('db_upsertZone(z, "DEMAND")')
    demand_created = source.find("created := true", demand_upsert)
    if demand_push < demand_upsert or demand_push > demand_created:
        raise AssertionError("Demand base time must be marked used only after demand zone upsert.")

    supply_push = source.find("array.push(used_supply_base_times, baseTime)")
    supply_upsert = source.find('db_upsertZone(z, "SUPPLY")')
    supply_created = source.find("created := true", supply_upsert)
    if supply_push < supply_upsert or supply_push > supply_created:
        raise AssertionError("Supply base time must be marked used only after supply zone upsert.")


if __name__ == "__main__":
    main()
