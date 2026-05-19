from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
STRATEGY = ROOT / "scripts/pinescript/strategies/SND_Strategy.pine"


def _require(source: str, needles: list[str], label: str) -> None:
    missing = [needle for needle in needles if needle not in source]
    if missing:
        raise AssertionError(f"{label} missing:\n" + "\n".join(missing))


def _forbid(source: str, needles: list[str], label: str) -> None:
    present = [needle for needle in needles if needle in source]
    if present:
        raise AssertionError(f"{label} must not contain:\n" + "\n".join(present))


def main() -> None:
    strategy = STRATEGY.read_text(encoding="utf-8")
    continuation_body = strategy[
        strategy.index("is_continuation_zone(int baseIdx, bool isDemand) =>") :
        strategy.index(
            "\nhas_better_continuation_base(",
            strategy.index("is_continuation_zone(int baseIdx, bool isDemand) =>"),
        )
    ]
    live_scan = strategy[
        strategy.index("if barstate.isconfirmed and bar_index > 10") :
        strategy.index("if barstate.isconfirmed and not initial_scan_done", strategy.index("if barstate.isconfirmed and bar_index > 10"))
    ]
    historical_scan = strategy[
        strategy.index("if barstate.isconfirmed and not initial_scan_done") :
        strategy.index("\nisValidSwingForLiquidity(", strategy.index("if barstate.isconfirmed and not initial_scan_done"))
    ]

    _require(
        strategy,
        [
            "enable_continuation_zones = true",
            "is_continuation_zone(int baseIdx, bool isDemand) =>",
            "float baseBodyHigh = math.max(open[baseIdx], close[baseIdx])",
            "float baseBodyLow = math.min(open[baseIdx], close[baseIdx])",
            "float continuation_range_atr = 1.8",
            "float continuation_max_body_pct = 0.85",
            "bool bearishBase = close[baseIdx] < open[baseIdx]",
            "bool bullishBase = close[baseIdx] > open[baseIdx]",
            "bool validBaseSide = isDemand ? bearishBase : bullishBase",
            "bool contaminatedContinuation = false",
            "bool closesAgainst = isDemand ? close[confirmIdx] < low[baseIdx] : close[confirmIdx] > high[baseIdx]",
            "bool confirmCandle = isDemand ? close[confirmIdx] > open[confirmIdx] and close[confirmIdx] > baseBodyHigh : close[confirmIdx] < open[confirmIdx] and close[confirmIdx] < baseBodyLow",
            "result := compactBase and validBaseSide and not contaminatedContinuation and confirmsAway",
            "is_preferred_continuation_zone(int baseIdx, bool isDemand) =>",
        ],
        "General continuation detector",
    )

    _forbid(
        strategy,
        [
            "gold_continuation_zones",
            "is_gold_continuation_zone(",
            "has_better_gold_continuation_base(",
            "is_preferred_gold_continuation_zone(",
            "validApproach",
            "shallowPullback",
            "reversalExtreme",
            "int newerIdx = baseIdx - scan",
            "overlapsNewer",
            "newerMoreDistal",
            "bearishDominantBase",
            "bullishDominantBase",
        ],
        "Gold-only continuation behavior",
    )

    if "(is_gold or is_xpt)" in continuation_body:
        raise AssertionError("Continuation detector must not restrict candidates to gold/XPT only")

    if live_scan.index("if is_preferred_continuation_zone(contBaseIdx, true)") > live_scan.index("[demandBaseIdx, demandLegCandles]"):
        raise AssertionError("Demand continuation zones must be attempted before simple displacement zones")
    if live_scan.index("if is_preferred_continuation_zone(contBaseIdx, false)") > live_scan.index("[supplyBaseIdx, supplyLegCandles]"):
        raise AssertionError("Supply continuation zones must be attempted before simple displacement zones")
    demand_live_block = live_scan[
        live_scan.index("bool demandContinuationCreated") :
        live_scan.index("if barstate.isconfirmed and bar_index > 10", live_scan.index("bool demandContinuationCreated") + 1)
    ]
    if "if is_preferred_continuation_zone(contBaseIdx, true) and not demandContinuationCreated" in demand_live_block:
        raise AssertionError("Demand continuation scan must allow multiple non-overlapping candidates in the same push")
    if "if not demandContinuationCreated" not in demand_live_block:
        raise AssertionError("Demand displacement fallback must still run only when no continuation zone was created")
    if historical_scan.index("if is_preferred_continuation_zone(displacementOffset, true)") > historical_scan.index("[histDemandBaseIdx, histDemandLegCandles]"):
        raise AssertionError("Historical demand continuation zones must be attempted before simple displacement zones")
    if historical_scan.index("if is_preferred_continuation_zone(displacementOffset, false)") > historical_scan.index("[histSupplyBaseIdx, histSupplyLegCandles]"):
        raise AssertionError("Historical supply continuation zones must be attempted before simple displacement zones")

    print("SND continuation zone static contract passed")


if __name__ == "__main__":
    main()
