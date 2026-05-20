from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
STRATEGY = ROOT / "scripts/pinescript/strategies/SND_Strategy.pine"


def _body(source: str, start_marker: str, end_marker: str) -> str:
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[start:end]


def main() -> None:
    strategy = STRATEGY.read_text(encoding="utf-8")
    strategy_header = _body(strategy, 'strategy("Institutional Liquidity Protocol [Pro]"', "// ============================================================================")
    supply_mitigation = _body(
        strategy,
        "int supplySize = array.size(supplyZones)",
        "if show_zones and show_demand_zones and cached_demand_size > 0 and barstate.isconfirmed",
    )

    required = [
        "max_labels_count                = 500",
        "max_boxes_count                 = 500",
        "max_lines_count                 = 500",
        "bool wick_into_supply = z.leftZone and not na(z.departureEndBarIndex) and bar_index > z.departureEndBarIndex and current_high >= z.bottom",
        "array.set(supplyZones, i, z)",
        "if close_inside_supply or close_above_zone or isTooOld or (invalidate_on_wick and wick_into_supply)",
        "remove_zone_all_arrays(false, i)",
    ]
    missing = [needle for needle in required if needle not in strategy]
    if missing:
        raise AssertionError("Missing supply visual/mitigation contract:\n" + "\n".join(missing))

    forbidden_header = [
        "max_labels_count                = 50,",
        "max_boxes_count                 = 50,",
        "max_lines_count                 = 50,",
    ]
    present_header = [needle for needle in forbidden_header if needle in strategy_header]
    if present_header:
        raise AssertionError("Drawing limits must stay raised:\n" + "\n".join(present_header))

    forbidden_mitigation = [
        "bool wick_above_zone = current_high > z.top",
        "invalidate_on_wick and wick_above_zone",
        "bool wick_into_supply = current_high >= z.bottom",
    ]
    present_mitigation = [needle for needle in forbidden_mitigation if needle in supply_mitigation]
    if present_mitigation:
        raise AssertionError("Supply wick mitigation must require post-departure return into zone:\n" + "\n".join(present_mitigation))

    print("SND supply visual and mitigation static contract passed")


if __name__ == "__main__":
    main()
