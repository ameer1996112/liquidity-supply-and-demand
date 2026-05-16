from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
STRATEGY = ROOT / "scripts/pinescript/strategies/SND_Strategy.pine"


def main() -> None:
    strategy = STRATEGY.read_text(encoding="utf-8")

    required = [
        "const float MAX_BASE_RANGE_ATR_FOREX = 1.2",
        "const float MAX_BASE_RANGE_ATR_WIDE_MARKET = 1.8",
        "float max_base_range_atr_mult = (is_gold or is_index or is_futures or is_xpt) ? MAX_BASE_RANGE_ATR_WIDE_MARKET : MAX_BASE_RANGE_ATR_FOREX",
        "float max_base_range = atr14 * max_base_range_atr_mult",
        "bool baseTooLarge = not na(max_base_range) and max_base_range > 0 and (baseHigh - baseLow) > max_base_range",
        "proceed_creation := proceed_creation and not baseTooLarge",
    ]

    missing = [item for item in required if item not in strategy]
    if missing:
        raise AssertionError("Missing oversized zone filter markers:\n" + "\n".join(missing))

    forbidden = [
        "if (zTop - zBottom) > max_zone_size\n                true  // No-op, keep current range",
        "bool zoneTooLarge = not na(max_zone_size) and max_zone_size > 0 and (zTop - zBottom) > max_zone_size",
        "zTop := na\n                zBottom := na",
    ]

    for needle in forbidden:
        if needle in strategy:
            raise AssertionError("Oversized zone filter must not keep the old no-op branch")

    print("SND oversized zone filter static contract passed")


if __name__ == "__main__":
    main()
