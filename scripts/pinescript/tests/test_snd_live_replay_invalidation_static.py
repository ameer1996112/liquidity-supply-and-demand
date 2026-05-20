from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
STRATEGY = ROOT / "scripts/pinescript/strategies/SND_Strategy.pine"


def _body(source: str, start_marker: str, end_marker: str) -> str:
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[start:end]


def main() -> None:
    strategy = STRATEGY.read_text(encoding="utf-8")

    header = _body(
        strategy,
        'strategy("Institutional Liquidity Protocol [Pro]",',
        "commission_type",
    )
    if "calc_on_every_tick              = true" not in header:
        raise AssertionError("Regular strategy must calculate on every tick so live/replay wick invalidation can delete breached zones before the bar closes")

    demand_tick_lifecycle = _body(
        strategy,
        "// Real-time/Replay boundary invalidation on every tick/bar\nint demandLifecycleSizeAll = array.size(demandZones)",
        "int demandLifecycleSize = array.size(demandZones)",
    )
    supply_tick_lifecycle = _body(
        strategy,
        "// Real-time/Replay boundary invalidation on every tick/bar\nint supplyLifecycleSizeAll = array.size(supplyZones)",
        "int supplyLifecycleSize = array.size(supplyZones)",
    )

    for needle in [
        "if demandLifecycleSizeAll > 0",
        "if is_future_bar",
        "if invalidate_on_wick and low < z.bottom",
        'invalidateDemandZone(i, "SETUP_INVALID_WICK_BELOW_ZONE")',
    ]:
        if needle not in demand_tick_lifecycle:
            raise AssertionError(f"Demand live/replay tick invalidation missing {needle!r}")

    for needle in [
        "if supplyLifecycleSizeAll > 0",
        "if is_future_bar",
        "if invalidate_on_wick and high > z.top",
        'invalidateSupplyZone(i, "SETUP_INVALID_WICK_ABOVE_ZONE")',
    ]:
        if needle not in supply_tick_lifecycle:
            raise AssertionError(f"Supply live/replay tick invalidation missing {needle!r}")

    if "barstate.isconfirmed" in demand_tick_lifecycle or "barstate.isconfirmed" in supply_tick_lifecycle:
        raise AssertionError("Live/replay tick invalidation must not be gated by barstate.isconfirmed")

    print("SND live/replay invalidation static contract passed")


if __name__ == "__main__":
    main()
