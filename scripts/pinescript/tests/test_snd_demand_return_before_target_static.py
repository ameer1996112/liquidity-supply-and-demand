from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
STRATEGY = ROOT / "scripts/pinescript/strategies/SND_Strategy.pine"


def _body(source: str, start_marker: str, end_marker: str) -> str:
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[start:end]


def main() -> None:
    strategy = STRATEGY.read_text(encoding="utf-8")
    demand_lifecycle = _body(
        strategy,
        "if cached_demand_size > 0 and barstate.isconfirmed",
        "if cached_supply_size > 0 and barstate.isconfirmed",
    )
    required = [
        "bool demandDisplacementContinues = current_close > z.top and close > open",
        "if demandDisplacementContinues",
        "z.leftZone := true",
        "z.departureEndBarIndex := bar_index",
        "array.set(demandZones, i, z)",
        "bool demandProofPending = not z.targetSwept",
        "bool immediateBearishReturn = not na(z.departureEndBarIndex) and bar_index == z.departureEndBarIndex + 1 and close < open and demandProofPending and (closes_inside or wicks_into_zone or breaches_zone) and not current_bar_sweeping",
        "if immediateBearishReturn",
        'invalidateDemandZone(i, "SETUP_INVALID_DEMAND_IMMEDIATE_RETURN_BEFORE_TARGET")',
        "if is_future_bar and z.leftZone and demandProofPending and (closes_inside or wicks_into_zone or breaches_zone)",
    ]
    missing = [needle for needle in required if needle not in strategy]
    if missing:
        raise AssertionError("Missing demand return-before-target invalidation contract:\n" + "\n".join(missing))

    forbidden = [
        "if current_close > z.top and not z.leftZone",
        "if is_future_bar and z.leftZone and not z.liquiditySwept and (closes_inside or wicks_into_zone or breaches_zone)",
        "if is_future_bar and z.leftZone and not z.liquiditySwept and (closes_inside or breaches_zone) and not current_bar_sweeping",
        "if not immediateBearishReturn and is_future_bar and z.leftZone and demandProofPending",
    ]
    present = [needle for needle in forbidden if needle in demand_lifecycle]
    if present:
        raise AssertionError("Demand return-before-target rule must use target proof and wick returns:\n" + "\n".join(present))

    print("SND demand return-before-target invalidation static contract passed")


if __name__ == "__main__":
    main()
