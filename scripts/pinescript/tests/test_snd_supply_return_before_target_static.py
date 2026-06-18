from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
STRATEGY = ROOT / "scripts/pinescript/strategies/SND_Strategy.pine"


def _body(source: str, start_marker: str, end_marker: str) -> str:
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[start:end]


def main() -> None:
    strategy = STRATEGY.read_text(encoding="utf-8")
    supply_lifecycle = _body(
        strategy,
        "if cached_supply_size > 0 and barstate.isconfirmed",
        "int demandSize = array.size(demandZones)",
    )
    required = [
        "bool supplyDisplacementContinues = current_close < z.bottom and close < open",
        "if supplyDisplacementContinues",
        "z.leftZone := true",
        "z.departureEndBarIndex := bar_index",
        "array.set(supplyZones, i, z)",
        "bool supplyProofPending = not z.targetSwept",
        "bool immediateBullishReturn = not na(z.departureEndBarIndex) and bar_index == z.departureEndBarIndex + 1 and close > open and supplyProofPending and (closes_inside or wicks_into_zone or breaches_zone) and not current_bar_sweeping",
        "if immediateBullishReturn",
        'invalidateSupplyZone(i, "SETUP_INVALID_SUPPLY_IMMEDIATE_RETURN_BEFORE_TARGET")',
        "if is_future_bar and z.leftZone and supplyProofPending and (closes_inside or wicks_into_zone or breaches_zone)",
        "z.touchedPreSweep := true",
        "if not immediateBullishReturn and is_future_bar and z.leftZone and supplyProofPending and (closes_inside or wicks_into_zone or breaches_zone) and not current_bar_sweeping",
    ]
    missing = [needle for needle in required if needle not in strategy]
    if missing:
        raise AssertionError("Missing supply immediate-return invalidation contract:\n" + "\n".join(missing))

    forbidden = [
        'invalidateSupplyZone(i, "SETUP_INVALID_SUPPLY_FAST_RETURN_BEFORE_SWEEP")',
        "supply_fast_return_bars",
        'invalidateSupplyZone(i, "SETUP_INVALID_RETURN_BEFORE_PROOF")',
    ]
    present = [needle for needle in forbidden if needle in supply_lifecycle]
    if present:
        raise AssertionError("Supply immediate-return rule must stay narrow:\n" + "\n".join(present))

    print("SND supply immediate-return invalidation static contract passed")


if __name__ == "__main__":
    main()
