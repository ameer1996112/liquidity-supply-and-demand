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
    supply_lifecycle = _body(
        strategy,
        "int supplySize = array.size(supplyZones)",
        "if show_zones and show_demand_zones",
    )

    required = [
        "bool close_above_zone = current_close > z.top",
        "bool wick_above_zone  = current_high > z.top",
        "bool returned_before_liq_sweep = require_liquidity_sweep and not touch_sweep_now and z.leftZone and (current_high >= z.bottom or z.mitigated) and (not z.liquidityValid or not z.liquiditySwept or na(z.liquiditySweptBarIndex) or bar_index <= z.liquiditySweptBarIndex)",
        "int confirmationBar = not na(z.departureEndBarIndex) ? z.departureEndBarIndex : z.createdBarIndex",
        "int invalidationStartBar = not na(z.firstInvalidBarIndex) ? z.firstInvalidBarIndex : confirmationBar + 1",
        "bool canJudgeInvalidation = afterConfirmation and departedAfterConfirmation",
        "bool validSweepOrProof = z.liquidityValid and z.liquiditySwept",
        "bool gatedReturnedBeforeLiqSweep = canJudgeInvalidation and not validSweepOrProof and returned_before_liq_sweep",
        "bool gatedReturnedInvalidAfterLeft = canJudgeInvalidation and not validSweepOrProof and returned_invalid_after_left",
        "bool gatedCloseAboveZone = canJudgeInvalidation and not validSweepOrProof and close_above_zone",
        "bool gatedWickAboveZone = canJudgeInvalidation and not validSweepOrProof and invalidate_on_wick and wick_above_zone",
        "if gatedReturnedBeforeLiqSweep or gatedReturnedInvalidAfterLeft or gatedCloseAboveZone or gatedWickAboveZone or isTooOld",
        "remove_zone_all_arrays(false, i)",
    ]
    missing = [needle for needle in required if needle not in supply_lifecycle]
    if missing:
        raise AssertionError("Missing supply return-before-target invalidation contract:\n" + "\n".join(missing))

    forbidden = [
        "supplyProofPending",
        "immediateBullishReturn",
        "SETUP_INVALID_SUPPLY_IMMEDIATE_RETURN_BEFORE_TARGET",
        "if is_future_bar and z.leftZone and supplyProofPending and (closes_inside or wicks_into_zone or breaches_zone)",
    ]
    present = [needle for needle in forbidden if needle in supply_lifecycle]
    if present:
        raise AssertionError("Supply return-before-target rule must use the current lifecycle gate:\n" + "\n".join(present))

    print("SND supply return-before-target invalidation static contract passed")


if __name__ == "__main__":
    main()
