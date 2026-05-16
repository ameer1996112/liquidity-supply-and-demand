from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
STRATEGY = ROOT / "scripts/pinescript/strategies/SND_Strategy.pine"


def main() -> None:
    strategy = STRATEGY.read_text(encoding="utf-8")
    continuation_body = strategy[
        strategy.index("is_continuation_zone(int baseIdx, bool isDemand) =>") :
        strategy.index("\nhas_better_continuation_base(", strategy.index("is_continuation_zone(int baseIdx, bool isDemand) =>"))
    ]

    required = [
        'enable_continuation_zones = input.bool(true, "Detect Continuation/Base Zones", group="③ Zone Engine")',
        "is_continuation_zone(int baseIdx, bool isDemand) =>",
        "float continuation_range_atr = (is_gold or is_index or is_futures or is_xpt) ? 1.8 : 1.2",
        "float continuation_max_body_pct = (is_gold or is_index or is_futures or is_xpt) ? 0.65 : 0.70",
        "bool bearishDominantBase =",
        "bool bullishDominantBase =",
        "bool validBaseSide = isDemand ? bearishDominantBase : bullishDominantBase",
        "bool confirmsAway = false",
        "close[confirmIdx] > high[baseIdx]",
        "close[confirmIdx] < low[baseIdx]",
        "is_preferred_continuation_zone(int baseIdx, bool isDemand) =>",
        "if is_preferred_continuation_zone(demandContBaseIdx, true)",
        "if is_preferred_continuation_zone(supplyContBaseIdx, false)",
        "if is_preferred_continuation_zone(i, true)",
        "if is_preferred_continuation_zone(i, false)",
    ]

    for needle in required:
        if needle not in strategy:
            raise AssertionError(f"Missing continuation zone contract: {needle}")

    forbidden = [
        "is_gold_continuation_zone(",
        "has_better_gold_continuation_base(",
        "is_preferred_gold_continuation_zone(",
        "gold_continuation_zones",
        "gold_continuation_zones and",
    ]

    for needle in forbidden:
        if needle in strategy:
            raise AssertionError(f"Continuation detector must not keep gold-only behavior: {needle}")

    if "(is_gold or is_xpt)" in continuation_body:
        raise AssertionError("Continuation detector must not restrict candidates to gold/XPT only")

    print("SND continuation zone static contract passed")


if __name__ == "__main__":
    main()
