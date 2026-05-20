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
        strategy.index("is_continuation_zone_for_leg(int baseIdx, int displacementStartIdx, bool isDemand) =>") :
        strategy.index(
            "\nis_continuation_zone(int baseIdx, bool isDemand) =>",
            strategy.index("is_continuation_zone_for_leg(int baseIdx, int displacementStartIdx, bool isDemand) =>"),
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
            'gold_continuation_zones = input.bool(true, "detect_continuation_zones"',
            "is_continuation_zone_for_leg(int baseIdx, int displacementStartIdx, bool isDemand) =>",
            "bool enabled = gold_continuation_zones",
            "is_continuation_zone(int baseIdx, bool isDemand) =>",
            "is_continuation_zone_for_leg(baseIdx, 0, isDemand)",
            "float baseBodyHigh = math.max(open[baseIdx], close[baseIdx])",
            "float baseBodyLow = math.min(open[baseIdx], close[baseIdx])",
            "bool wideMarket = is_gold or is_xpt or is_index or is_futures",
            "float contAtrCap = wideMarket ? 1.8 : 1.2",
            "float contBodyPct = wideMarket ? 0.65 : 0.55",
            "bool compactBase = baseRange > syminfo.mintick and baseRange <= atr14 * contAtrCap and baseBody <= baseRange * contBodyPct",
            "bool validBaseSide = is_valid_zone_base_candle(baseIdx, isDemand, true)",
            "bool contaminatedContinuation = false",
            "if confirmIdx < displacementStartIdx",
            "bool closesAgainst = isDemand ? close[confirmIdx] < low[baseIdx] : close[confirmIdx] > high[baseIdx]",
            "bool confirmCandle = isDemand ? close[confirmIdx] > open[confirmIdx] and close[confirmIdx] > baseBodyHigh : close[confirmIdx] < open[confirmIdx] and close[confirmIdx] < baseBodyLow",
            "result := compactBase and validBaseSide and not contaminatedContinuation and confirmsAway",
            "has_better_continuation_base(int baseIdx, int displacementStartIdx, bool isDemand) =>",
            "for scanIdx = displacementStartIdx + 1 to baseIdx - 1",
            "bool overlapsRightOrigin = not (high[scanIdx] < low[baseIdx] or low[scanIdx] > high[baseIdx])",
            "is_preferred_continuation_zone(int baseIdx, int displacementStartIdx, bool isDemand) =>",
            "find_preferred_continuation_base(int displacementStartIdx, bool isDemand) =>",
            "int candidateIdx = displacementStartIdx + scan",
            "result := candidateIdx",
            "break",
        ],
        "General continuation detector",
    )

    _forbid(
        strategy,
        [
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
            "if na(demandBaseIdx)\n        for contBaseIdx",
            "if na(supplyBaseIdx)\n        for contBaseIdx",
            "if na(histDemandBaseIdx) and is_preferred",
            "if na(histSupplyBaseIdx) and is_preferred",
        ],
        "Gold-only continuation behavior",
    )

    if "(is_gold or is_xpt)" in continuation_body:
        raise AssertionError("Continuation detector must not restrict candidates to gold/XPT only")

    if live_scan.index("int demandContinuationBaseIdx = find_preferred_continuation_base(0, true)") < live_scan.index("[demandBaseIdx, demandLegCandles]"):
        raise AssertionError("Demand continuation zones must be scanned after simple displacement detection")
    if live_scan.index("int supplyContinuationBaseIdx = find_preferred_continuation_base(0, false)") < live_scan.index("[supplyBaseIdx, supplyLegCandles]"):
        raise AssertionError("Supply continuation zones must be scanned after simple displacement detection")
    if "if not na(demandContinuationBaseIdx)" not in live_scan:
        raise AssertionError("Demand continuation scan should create at most one preferred live zone")
    if "if not na(supplyContinuationBaseIdx)" not in live_scan:
        raise AssertionError("Supply continuation scan should create at most one preferred live zone")
    if historical_scan.index("int histDemandContinuationBaseIdx = find_preferred_continuation_base(displacementOffset, true)") < historical_scan.index("[histDemandBaseIdx, histDemandLegCandles]"):
        raise AssertionError("Historical demand continuation zones must be scanned after simple displacement detection")
    if historical_scan.index("int histSupplyContinuationBaseIdx = find_preferred_continuation_base(displacementOffset, false)") < historical_scan.index("[histSupplyBaseIdx, histSupplyLegCandles]"):
        raise AssertionError("Historical supply continuation zones must be scanned after simple displacement detection")
    if "createZone(histDemandContinuationBaseIdx, true, true, 1, 1, nextZoneId, false)" not in historical_scan:
        raise AssertionError("Historical demand continuation should create only the selected canonical base")
    if "createZone(histSupplyContinuationBaseIdx, false, true, 1, 1, nextZoneId, false)" not in historical_scan:
        raise AssertionError("Historical supply continuation should create only the selected canonical base")
    if "createZone(demandContinuationBaseIdx, true, false, 1, 1, nextZoneId, false)" not in live_scan:
        raise AssertionError("Live demand continuation must keep base-candle boundaries")
    if "createZone(supplyContinuationBaseIdx, false, false, 1, 1, nextZoneId, false)" not in live_scan:
        raise AssertionError("Live supply continuation must keep base-candle boundaries")
    if "createZone(supplyBaseIdx, false, false, 1, supplyLegCandles, nextZoneId, true)" not in live_scan:
        raise AssertionError("Standard supply displacement zones must still allow departure wick extension")

    print("SND continuation zone static contract passed")


if __name__ == "__main__":
    main()
