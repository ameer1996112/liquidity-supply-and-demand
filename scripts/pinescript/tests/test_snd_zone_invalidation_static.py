from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
STRATEGY = ROOT / "scripts/pinescript/strategies/SND_Strategy.pine"


def _body(source: str, start_marker: str, end_marker: str) -> str:
    if start_marker not in source:
        return ""
    start = source.index(start_marker)
    if end_marker not in source[start:]:
        return source[start:]
    end = source.index(end_marker, start)
    return source[start:end]


def main() -> None:
    strategy = STRATEGY.read_text(encoding="utf-8")

    removal_helper = _body(
        strategy,
        "remove_zone_all_arrays(bool isDemand, int idx) =>",
        "getLiquidityDistance(Core.Zone z, bool isSupply) =>",
    )
    for needle in [
        "db_markInactive(z.id, \"removed\")",
        "clear_visual_lifecycle(z.id)",
        "box.delete(z.boxId)",
        "array.remove(demandZones, idx)",
        "array.remove(supplyZones, idx)",
    ]:
        if needle not in removal_helper:
            raise AssertionError(f"remove helper missing {needle!r}")

    demand_lifecycle = _body(
        strategy,
        "int demandSize = array.size(demandZones)",
        "int supplySize = array.size(supplyZones)",
    )
    for needle in [
        "bool canJudgeInvalidation = afterConfirmation and departedAfterConfirmation",
        "bool validSweepOrProof = z.liquidityValid and z.liquiditySwept",
        "bool gatedReturnedBeforeLiqSweep = canJudgeInvalidation and not validSweepOrProof and returned_before_liq_sweep",
        "bool gatedReturnedInvalidAfterLeft = canJudgeInvalidation and not validSweepOrProof and returned_invalid_after_left",
        "bool gatedCloseBelowZone = canJudgeInvalidation and not validSweepOrProof and close_below_zone",
        "bool gatedWickBelowZone = canJudgeInvalidation and not validSweepOrProof and invalidate_on_wick and wick_below_zone",
        "if gatedReturnedBeforeLiqSweep or gatedReturnedInvalidAfterLeft or gatedCloseBelowZone or gatedWickBelowZone or isTooOld",
        'recordDiag(sameBarSweepOrder ? 303 : 302, true, bar_index - z.createdBarIndex, sameBarSweepOrder ? "same bar sweep order" : "returned pre sweep")',
        'recordDiag(305, true, bar_index - z.createdBarIndex, "close invalidated")',
        'recordDiag(304, true, bar_index - z.createdBarIndex, "wick invalidated")',
        'recordDiag(306, true, bar_index - z.createdBarIndex, "expired too early")',
        "remove_zone_all_arrays(true, i)",
        "z.isHistorical",
    ]:
        if needle not in demand_lifecycle:
            raise AssertionError(f"demand lifecycle missing {needle!r}")
    for forbidden in [
        "clearDemandLiquidityVisual(i)",
        "invalidateDemandZone(i, \"SETUP_INVALID_RETURN_BEFORE_PROOF\")",
    ]:
        if forbidden in demand_lifecycle:
            raise AssertionError(f"demand lifecycle still has stale contract {forbidden!r}")

    supply_lifecycle = _body(
        strategy,
        "int supplySize = array.size(supplyZones)",
        "if show_zones and show_demand_zones",
    )
    for needle in [
        "bool canJudgeInvalidation = afterConfirmation and departedAfterConfirmation",
        "bool validSweepOrProof = z.liquidityValid and z.liquiditySwept",
        "bool gatedReturnedBeforeLiqSweep = canJudgeInvalidation and not validSweepOrProof and returned_before_liq_sweep",
        "bool gatedReturnedInvalidAfterLeft = canJudgeInvalidation and not validSweepOrProof and returned_invalid_after_left",
        "bool gatedCloseAboveZone = canJudgeInvalidation and not validSweepOrProof and close_above_zone",
        "bool gatedWickAboveZone = canJudgeInvalidation and not validSweepOrProof and invalidate_on_wick and wick_above_zone",
        "if gatedReturnedBeforeLiqSweep or gatedReturnedInvalidAfterLeft or gatedCloseAboveZone or gatedWickAboveZone or isTooOld",
        'recordDiag(sameBarSweepOrder ? 303 : 302, false, bar_index - z.createdBarIndex, sameBarSweepOrder ? "same bar sweep order" : "returned pre sweep")',
        'recordDiag(305, false, bar_index - z.createdBarIndex, "close invalidated")',
        'recordDiag(304, false, bar_index - z.createdBarIndex, "wick invalidated")',
        'recordDiag(306, false, bar_index - z.createdBarIndex, "expired too early")',
        "remove_zone_all_arrays(false, i)",
        "z.isHistorical",
    ]:
        if needle not in supply_lifecycle:
            raise AssertionError(f"supply lifecycle missing {needle!r}")
    for forbidden in [
        "clearSupplyLiquidityVisual(i)",
        "invalidateSupplyZone(i, \"SETUP_INVALID_RETURN_BEFORE_PROOF\")",
    ]:
        if forbidden in supply_lifecycle:
            raise AssertionError(f"supply lifecycle still has stale contract {forbidden!r}")

    create_zone = _body(
        strategy,
        "createZone(int baseIdx, bool isDemand, bool isHistorical, int candlesInBase, int legCandles, int zoneUZID, bool allowUsedBase = false) =>",
        "\nremove_zone_all_arrays(",
    )
    for needle in [
        "int baseTime = time[baseIdx]",
        "bool alreadyUsed = false",
        "if isDemand",
        "if array.includes(used_demand_base_times, baseTime)",
        "if array.includes(used_supply_base_times, baseTime)",
        'db_upsertZone(z, "DEMAND")',
        'db_upsertZone(z, "SUPPLY")',
        "array.push(used_demand_base_times, baseTime)",
        "array.push(used_supply_base_times, baseTime)",
    ]:
        if needle not in create_zone:
            raise AssertionError(f"createZone missing {needle!r}")
    demand_db = create_zone.index('db_upsertZone(z, "DEMAND")')
    demand_base_used = create_zone.index("array.push(used_demand_base_times, baseTime)")
    supply_db = create_zone.index('db_upsertZone(z, "SUPPLY")')
    supply_base_used = create_zone.index("array.push(used_supply_base_times, baseTime)")
    if not (demand_db < demand_base_used and supply_db < supply_base_used):
        raise AssertionError("Accepted-zone creation ordering changed")

    print("SND zone invalidation static contract passed")


if __name__ == "__main__":
    main()
