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
    demand_lifecycle = _body(
        strategy,
        "int demandSize = array.size(demandZones)",
        "int supplySize = array.size(supplyZones)",
    )

    required = [
        "bool close_below_zone = current_close < z.bottom",
        "bool wick_below_zone  = current_low < z.bottom",
        "bool returned_before_liq_sweep = require_liquidity_sweep and not touch_sweep_now and z.leftZone and (current_low <= z.top or z.mitigated) and (not z.liquidityValid or not z.liquiditySwept or na(z.liquiditySweptBarIndex) or bar_index <= z.liquiditySweptBarIndex)",
        "int confirmationBar = not na(z.departureEndBarIndex) ? z.departureEndBarIndex : z.createdBarIndex",
        "int invalidationStartBar = not na(z.firstInvalidBarIndex) ? z.firstInvalidBarIndex : confirmationBar + 1",
        "bool canJudgeInvalidation = afterConfirmation and departedAfterConfirmation",
        "bool validSweepOrProof = z.liquidityValid and z.liquiditySwept",
        "bool gatedReturnedBeforeLiqSweep = canJudgeInvalidation and not validSweepOrProof and returned_before_liq_sweep",
        "bool gatedReturnedInvalidAfterLeft = canJudgeInvalidation and not validSweepOrProof and returned_invalid_after_left",
        "bool gatedCloseBelowZone = canJudgeInvalidation and not validSweepOrProof and close_below_zone",
        "bool gatedWickBelowZone = canJudgeInvalidation and not validSweepOrProof and invalidate_on_wick and wick_below_zone",
        "if gatedReturnedBeforeLiqSweep or gatedReturnedInvalidAfterLeft or gatedCloseBelowZone or gatedWickBelowZone or isTooOld",
        "remove_zone_all_arrays(true, i)",
    ]
    missing = [needle for needle in required if needle not in demand_lifecycle]
    if missing:
        raise AssertionError("Missing demand return-before-target invalidation contract:\n" + "\n".join(missing))

    forbidden = [
        "demandProofPending",
        "immediateBearishReturn",
        "SETUP_INVALID_DEMAND_IMMEDIATE_RETURN_BEFORE_TARGET",
        "if is_future_bar and z.leftZone and demandProofPending and (closes_inside or wicks_into_zone or breaches_zone)",
    ]
    present = [needle for needle in forbidden if needle in demand_lifecycle]
    if present:
        raise AssertionError("Demand return-before-target rule must use the current lifecycle gate:\n" + "\n".join(present))

    print("SND demand return-before-target invalidation static contract passed")


if __name__ == "__main__":
    main()
