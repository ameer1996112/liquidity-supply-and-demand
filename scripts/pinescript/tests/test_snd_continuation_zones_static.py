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
        "float continuation_max_body_pct = (is_gold or is_index or is_futures or is_xpt) ? 0.85 : 0.70",
        "bool bearishDominantBase =",
        "bool bullishDominantBase =",
        "bool validBaseSide = isDemand ? bearishDominantBase : bullishDominantBase",
        "bool confirmsAway = false",
        "bool contaminatedContinuation = false",
        "bool closesAgainst = isDemand ? close[confirmIdx] < low[baseIdx] : close[confirmIdx] > high[baseIdx]",
        "not contaminatedContinuation and confirmsAway",
        "close[confirmIdx] > high[baseIdx]",
        "close[confirmIdx] < low[baseIdx]",
        "is_preferred_continuation_zone(int baseIdx, bool isDemand) =>",
        "if is_preferred_continuation_zone(demandContBaseIdx, true)",
        "if is_preferred_continuation_zone(supplyContBaseIdx, false)",
        "if is_preferred_continuation_zone(i, true)",
        "if is_preferred_continuation_zone(i, false)",
        "maybeCreateDetectedZone(replayOffset + 4, true, isHistorical, 4, nextCounter, rememberReplayAttempt)",
        "maybeCreateDetectedZone(replayOffset + 4, false, isHistorical, 4, nextCounter, rememberReplayAttempt)",
        "maybeCreateDetectedZone(i, true, true, 4, global_zone_id_counter, false)",
        "maybeCreateDetectedZone(i, false, true, 4, global_zone_id_counter, false)",
        "is_origin_base_cluster_member(int scanIdx, int anchorIdx, bool isDemand) =>",
        "bool overlapsAnchor = not (high[scanIdx] < low[anchorIdx] or low[scanIdx] > high[anchorIdx])",
        "bool neutralBase = scanRange > 0 and scanBody <= scanRange * 0.50",
        "bool foundSameSideOrigin = isDemand ? Utils.is_bearish(close[candidateBaseIdx], open[candidateBaseIdx]) : Utils.is_bullish(close[candidateBaseIdx], open[candidateBaseIdx])",
        "bool clusterMember = is_origin_base_cluster_member(olderIdx, anchorIdx, isDemand)",
        "if sameSideBase\n                firstBaseIdx := olderIdx",
        "foundSameSideOrigin := true",
        "foundSameSideOrigin ? firstBaseIdx : na",
        "if na(resolvedBaseIdx)",
        "mark_zone_rejected(REASON_REJECTED_CONTAMINATED_ORIGIN)",
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
        "validApproach",
        "shallowPullback",
        "reversalExtreme",
        "int newerIdx = baseIdx - scan",
        "overlapsNewer",
        "newerMoreDistal",
    ]

    for needle in forbidden:
        if needle in strategy:
            raise AssertionError(f"Continuation detector must not keep gold-only behavior: {needle}")

    if "(is_gold or is_xpt)" in continuation_body:
        raise AssertionError("Continuation detector must not restrict candidates to gold/XPT only")

    resolver_body = strategy[
        strategy.index("resolve_first_base_idx(int candidateBaseIdx, bool isDemand) =>") :
        strategy.index("\nmaybeCreateDetectedZone(", strategy.index("resolve_first_base_idx(int candidateBaseIdx, bool isDemand) =>"))
    ]
    if "olderMoreDistal" in resolver_body:
        raise AssertionError("Base resolver must choose the first same-side origin, not only the most distal origin")

    print("SND continuation zone static contract passed")


if __name__ == "__main__":
    main()
