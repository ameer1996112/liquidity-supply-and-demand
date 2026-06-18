from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
INDICATOR = ROOT / "scripts/pinescript/indicators/SND_Raw_RD_Forex.pine"


def main() -> None:
    indicator = INDICATOR.read_text(encoding="utf-8")

    required = [
        'useStrategyZoneRulesOnly = input.bool(true, "Use Strategy Zone Rules Only")',
        'zoneDetectionMode = input.string("All", "Zone Detection Mode", options = ["Classic", "Sweep Origin", "Displacement Origin", "All"])',
        'maxLiquidityDistanceATRMultiplier = input.float(2.0, "Max Liquidity Distance ATR"',
        'detectSweepOriginZones = input.bool(true, "Detect Sweep-Origin Zones")',
        'detectDisplacementOriginZones = input.bool(true, "Detect Displacement-Origin Zones")',
        'zoneSourceMode = input.string("Wick To Body", "Zone Source Mode", options = ["Wick To Body", "Full Candle", "Body Only", "Auto"])',
        'allowParentAndChildZones = input.bool(true, "Allow Parent And Child Zones")',
        'enableContinuationZones = input.bool(true, "Enable Continuation Zones")',
        'minBarsBeforeInvalidation = input.int(2, "Min Bars Before Invalidation"',
        'const string MODEL_SWEEP_ORIGIN = "SWEEP_ORIGIN"',
        'const string MODEL_DISPLACEMENT_ORIGIN = "DISPLACEMENT_ORIGIN"',
        "bool displayBeforeLiquidity",
        "float candidateScore",
        "string creationReason",
        'showFreshStrategyZones = input.bool(true, "Show Fresh Strategy Zones")',
        "isStrategyZoneModel(string model) =>",
        "zoneFillColorForZone(RawZone z) =>",
        "zoneFillColor(z.demand, z.model)",
        "zoneHasPrimaryLiquidityEvidence(RawZone z) =>",
        "z.active and (z.liquidityLinked or zoneHasPrimaryLiquidityEvidence(z) or drawUnlinkedActiveZones())",
        "maxLiquidityDistance() =>",
        "liquidityCloseEnoughToZone(float candidatePrice, float zoneBoundary) =>",
        "bool closeEnough = liquidityCloseEnoughToZone(candidateLevel, out.top)",
        "bool closeEnough = liquidityCloseEnoughToZone(candidateLevel, out.bottom)",
        "[extendedAccTop, extendedAccBottom] = extendFormationWickBounds(baseIdx, demand, legCandles, true, accTop, accBottom)",
        "finalTop := top",
        "finalBottom := bottom",
        "originSourceBounds(int sourceIdx, bool demand, string model) =>",
        'string resolvedSourceMode = model == MODEL_DISPLACEMENT_ORIGIN ? "Full Candle"',
        "if model == MODEL_DISPLACEMENT_ORIGIN",
        "extendFormationWickBounds(sourceIdx, demand",
        "originSourceOk(int offset, bool demand) =>",
        "oppositeDirectional or (isSmallBodyBase(offset) and not sameDirectional)",
        "originCandidateScore(int sourceIdx, bool demand, bool sweepDetected, bool displacementDetected, float top, float bottom) =>",
        "displacementDetected and sourceIdx <= formationLegScanBars",
        "bool singleCandleImpulse = directional and quality and (rangeImpulse or bodyImpulse)",
        "bool multiCandleImpulse = false",
        "float legOpen = open",
        "legOpen := open[scan]",
        "multiCandleImpulse := legCount > 1 and legDirectional and legBodyPct >= minImpulseBodyPercent and (legRangeImpulse or legBodyImpulse)",
        "singleCandleImpulse or multiCandleImpulse",
        "originSourceAtLocalExtreme(int sourceIdx, bool demand) =>",
        "createOriginZone(int sourceIdx, bool demand, int zoneId, string model, int confirmationBar, bool sweepDetected, bool displacementDetected) =>",
        "tryCreateSweepOriginZone(bool demand, int zoneId) =>",
        "tryCreateDisplacementOriginZone(bool demand, int zoneId) =>",
        "directionalCountBetween(int startOffset, int endOffset, bool demand) =>",
        "resolveStandardZoneCandidateAt(int eventStartIdx, int candidateBaseIdx, bool demand, int startOffset) =>",
        "resolveStandardFallbackCandidate(bool demand) =>",
        "if not continuationMode and na(baseIdx)",
        "tryCreateStackedStandardZones(bool demand, bool primaryValid, int primaryBaseIdx, int zoneId) =>",
        "if accSuppressedSymbol() and classicDetectionEnabled() and eventDirectional and createdLimit > 0",
        "tryCreateParentClusterZone(int baseIdx, bool demand, int zoneId, string model, int confirmationIdx, int confirmationBar) =>",
        "int parentBaseIdx = immediateBaseClusterOrigin(baseIdx, demand)",
        'if allowParentAndChildZones or overlapMode == "Keep Both"',
        "z.displayBeforeLiquidity := true",
        "z.zoneBox := drawUnlinkedActiveZones() ? createZoneBox(originBar, top, bottom, demand, model) : na",
        "[top, bottom] = originSourceBounds(sourceIdx, demand, model)",
        "if classicDetectionEnabled()",
        "tryCreateParentClusterZone(demandBaseIdx, true, nextZoneId, demandModel, demandConfirmationIdx, demandConfirmationBar)",
        "tryCreateParentClusterZone(supplyBaseIdx, false, nextZoneId, supplyModel, supplyConfirmationIdx, supplyConfirmationBar)",
        "tryCreateStackedStandardZones(true, demandValid, demandBaseIdx, nextZoneId)",
        "tryCreateStackedStandardZones(false, supplyValid, supplyBaseIdx, nextZoneId)",
        "model == MODEL_SWEEP_ORIGIN or model == MODEL_DISPLACEMENT_ORIGIN",
        'zoneDetectionMode == "Classic" or (zoneDetectionMode == "All" and not useStrategyZoneRulesOnly)',
        'detectSweepOriginZones and (zoneDetectionMode == "Sweep Origin" or (zoneDetectionMode == "All" and not useStrategyZoneRulesOnly))',
        "detectDisplacementOriginZones and",
        "int createdCount = 0",
        "int createdLimit = 1",
        "for eventScan = 1 to displacementScanBars",
        "scanStart := eventScan",
        "bool foundSourceCluster = false",
        "int off = scanStart + scan",
        "bool sourceOk = originSourceOk(off, demand)",
        "string candidateDuplicateReason = candidateBoundsValid ? duplicateRejectReason(candidateTop, candidateBottom, demand, candidateOriginBar, MODEL_DISPLACEMENT_ORIGIN, bar_index) : \"\"",
        "if str.length(candidateDuplicateReason) > 0",
        "else if foundSourceCluster",
        "nextZoneId += demandOriginCreatedCount",
        "nextZoneId += supplyOriginCreatedCount",
        "bool afterHistoricalDelay = sourceIdx > minBarsBeforeInvalidation",
        "bool checkHistoricalInvalidation = afterHistoricalDelay and not (model == MODEL_DISPLACEMENT_ORIGIN and displacementDetected)",
        "else if checkHistoricalInvalidation and zoneInvalidatedAfterOrigin(top, bottom, sourceIdx, demand)",
        "zoneInvalidatedAfterOrigin(top, bottom, sourceIdx, demand)",
        "sweepOriginDetectionEnabled()",
        "displacementOriginDetectionEnabled()",
        "afterInvalidationDelay and",
    ]

    for needle in required:
        if needle not in indicator:
            raise AssertionError(f"Missing RD origin zone contract marker: {needle}")

    classic_gate = indicator.index("if classicDetectionEnabled()")
    sweep_gate = indicator.index("if sweepOriginDetectionEnabled()")
    displacement_gate = indicator.index("if displacementOriginDetectionEnabled()")
    pivot_scan = indicator.index("float pivotLow = ta.pivotlow")
    if not classic_gate < sweep_gate < displacement_gate < pivot_scan:
        raise AssertionError("RD origin zones must be created after classic candidates and before liquidity linking")

    forbidden = "[extendedTop, extendedBottom] = extendFormationWickBounds(baseIdx, demand, legCandles, true, top, bottom)"
    if forbidden in indicator:
        raise AssertionError("Standard Raw RD zones must use the origin candle bounds, not formation-leg wick expansion")

    print("SND Raw RD Forex origin zone static contract passed")


if __name__ == "__main__":
    main()
