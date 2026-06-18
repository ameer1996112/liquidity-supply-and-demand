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

    header = _body(
        strategy,
        'strategy("Institutional Liquidity Protocol [Pro]",',
        "commission_type",
    )
    if "calc_on_every_tick = false" not in header:
        raise AssertionError("Current strategy should remain on confirmed-bar calculation, not tick-by-tick replay invalidation")

    demand_lifecycle = _body(
        strategy,
        "int demandSize = array.size(demandZones)",
        "int supplySize = array.size(supplyZones)",
    )
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
        "bool gatedCloseBelowZone = canJudgeInvalidation and not validSweepOrProof and close_below_zone",
        "bool gatedWickBelowZone = canJudgeInvalidation and not validSweepOrProof and invalidate_on_wick and wick_below_zone",
        "remove_zone_all_arrays(true, i)",
        "remove_zone_all_arrays(false, i)",
    ]:
        if needle not in demand_lifecycle and needle not in supply_lifecycle:
            raise AssertionError(f"Current confirmed-bar lifecycle missing {needle!r}")

    for forbidden in [
        "demandLifecycleSizeAll",
        "supplyLifecycleSizeAll",
        "calc_on_every_tick              = true",
        "if invalidate_on_wick and low < z.bottom",
        "if invalidate_on_wick and high > z.top",
    ]:
        if forbidden in strategy:
            raise AssertionError(f"Live replay contract should not contain stale tick path {forbidden!r}")

    print("SND live/replay invalidation static contract passed")


if __name__ == "__main__":
    main()
