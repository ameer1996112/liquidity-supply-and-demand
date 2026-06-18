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

    create_zone = _body(
        strategy,
        "createZone(int baseIdx, bool isDemand, bool isHistorical, int candlesInBase, int legCandles, int zoneUZID",
        "\nremove_zone_all_arrays(",
    )
    for needle in [
        "z.departureEndBarIndex := bar_index",
        "z.firstInvalidBarIndex := bar_index + 1",
        "z.structureBreakBarIndex := na",
        'z.stateReason := "CONFIRMED_WAIT_RUNTIME_DEPARTURE"',
    ]:
        if needle not in create_zone:
            raise AssertionError(f"createZone missing lifecycle anchor {needle!r}")

    demand_pre_sweep = _body(
        strategy,
        "if cached_demand_size > 0 and barstate.isconfirmed",
        "if cached_supply_size > 0 and barstate.isconfirmed",
    )
    for needle in [
        "bool canTrackDemandPreSweepMitigation = bar_index >= demandInvalidationStartBar and not na(z.structureBreakBarIndex) and z.structureBreakBarIndex >= demandInvalidationStartBar",
        "if is_future_bar and z.leftZone and (closes_inside or breaches_zone) and not current_bar_sweeping and not z.liquiditySwept and canTrackDemandPreSweepMitigation",
    ]:
        if needle not in demand_pre_sweep:
            raise AssertionError(f"demand pre-sweep gate missing {needle!r}")
    for forbidden in [
        "if is_future_bar and z.leftZone and (closes_inside or breaches_zone) and not current_bar_sweeping and not z.liquiditySwept\n                    z.mitigated := true",
    ]:
        if forbidden in demand_pre_sweep:
            raise AssertionError(f"demand pre-sweep still has ungated mitigation {forbidden!r}")

    supply_pre_sweep = _body(
        strategy,
        "if cached_supply_size > 0 and barstate.isconfirmed",
        "int demandSize = array.size(demandZones)",
    )
    for needle in [
        "bool canTrackSupplyPreSweepMitigation = bar_index >= supplyInvalidationStartBar and not na(z.structureBreakBarIndex) and z.structureBreakBarIndex >= supplyInvalidationStartBar",
        "if is_future_bar and z.leftZone and (closes_inside or breaches_zone) and not current_bar_sweeping and not z.liquiditySwept and canTrackSupplyPreSweepMitigation",
    ]:
        if needle not in supply_pre_sweep:
            raise AssertionError(f"supply pre-sweep gate missing {needle!r}")
    for forbidden in [
        "if is_future_bar and z.leftZone and (closes_inside or breaches_zone) and not current_bar_sweeping and not z.liquiditySwept\n                    z.mitigated := true",
    ]:
        if forbidden in supply_pre_sweep:
            raise AssertionError(f"supply pre-sweep still has ungated mitigation {forbidden!r}")

    demand_lifecycle = _body(
        strategy,
        "int demandSize = array.size(demandZones)",
        "int supplySize = array.size(supplyZones)",
    )
    for needle in [
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
    ]:
        if needle not in demand_lifecycle:
            raise AssertionError(f"demand lifecycle gate missing {needle!r}")
    for forbidden in [
        "if returned_before_liq_sweep or returned_invalid_after_left or close_below_zone or wick_below_zone or isTooOld",
        "else if wick_below_zone",
        "if is_future_bar and z.leftZone and (closes_inside or breaches_zone) and not current_bar_sweeping and not z.liquiditySwept\n                    z.mitigated := true",
    ]:
        if forbidden in demand_lifecycle:
            raise AssertionError(f"demand lifecycle still has ungated invalidation {forbidden!r}")

    supply_lifecycle = _body(
        strategy,
        "int supplySize = array.size(supplyZones)",
        "if show_zones and show_demand_zones",
    )
    for needle in [
        "int confirmationBar = not na(z.departureEndBarIndex) ? z.departureEndBarIndex : z.createdBarIndex",
        "int invalidationStartBar = not na(z.firstInvalidBarIndex) ? z.firstInvalidBarIndex : confirmationBar + 1",
        "bool afterConfirmation = bar_index >= invalidationStartBar",
        "bool departedAfterConfirmation = not na(z.structureBreakBarIndex) and z.structureBreakBarIndex >= invalidationStartBar",
        "bool canJudgeInvalidation = afterConfirmation and departedAfterConfirmation",
        "bool validSweepOrProof = z.liquidityValid and z.liquiditySwept",
        "bool gatedReturnedBeforeLiqSweep = canJudgeInvalidation and not validSweepOrProof and returned_before_liq_sweep",
        "bool gatedReturnedInvalidAfterLeft = canJudgeInvalidation and not validSweepOrProof and returned_invalid_after_left",
        "bool gatedCloseAboveZone = canJudgeInvalidation and not validSweepOrProof and close_above_zone",
        "bool gatedWickAboveZone = canJudgeInvalidation and not validSweepOrProof and invalidate_on_wick and wick_above_zone",
        "if gatedReturnedBeforeLiqSweep or gatedReturnedInvalidAfterLeft or gatedCloseAboveZone or gatedWickAboveZone or isTooOld",
    ]:
        if needle not in supply_lifecycle:
            raise AssertionError(f"supply lifecycle gate missing {needle!r}")
    for forbidden in [
        "if returned_before_liq_sweep or returned_invalid_after_left or close_above_zone or wick_above_zone or isTooOld",
        "else if wick_above_zone",
        "if is_future_bar and z.leftZone and (closes_inside or breaches_zone) and not current_bar_sweeping and not z.liquiditySwept\n                    z.mitigated := true",
    ]:
        if forbidden in supply_lifecycle:
            raise AssertionError(f"supply lifecycle still has ungated invalidation {forbidden!r}")

    inspector = _body(
        strategy,
        "var table zoneInspector = na",
        "if not showZoneInspector",
    )
    for needle in [
        "string lifecycleDebug =",
        '"Origin"',
        '"Confirm"',
        '"InvStart"',
        '"CanJudge"',
        'table.cell(zoneInspector, 0, nextRow, "Lifecycle"',
    ]:
        if needle not in inspector:
            raise AssertionError(f"zone inspector missing lifecycle debug {needle!r}")

    print("SND strategy lifecycle gate static contract passed")


if __name__ == "__main__":
    main()
