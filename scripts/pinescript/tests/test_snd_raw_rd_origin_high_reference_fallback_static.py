from pathlib import Path


INDICATORS = [
    Path("scripts/pinescript/indicators/SND_Raw_RD_Forex.pine"),
    Path("scripts/pinescript/indicators/SND_Raw_RD_Forex_LAB.pine"),
    Path("scripts/pinescript/indicators/SND_Raw_RD_Forex_PROD.pine"),
]


def test_demand_origin_high_reference_fallback_exists_for_waiting_pivot_zones() -> None:
    for path in INDICATORS:
        source = path.read_text()

        assert "demandOriginHighReferenceLiquidity(RawZone z)" in source
        assert "bool priceAboveOrigin = not na(refPrice) and refPrice >= originHigh - tol" in source
        assert "if not refIsDemand and refCanSeed and inOriginWindow and priceAboveOrigin" in source
        assert "[originHighRefPrice, originHighRefBar, originHighRefDist] = demandOriginHighReferenceLiquidity(out)" in source
        assert 'bestSource := "ORIGIN_HIGH_REFERENCE"' in source
        assert 'bestSource == "ORIGIN_HIGH_REFERENCE" or bestSource == "OWN_ORIGIN" ? true : demandLegCount >= minLegCandles' in source
        assert "SELECTED_ORIGIN_HIGH_REFERENCE" in source


def test_debug_mode_always_shows_rejection_reason() -> None:
    for path in INDICATORS:
        source = path.read_text()

        assert "(showRejectedLiquidityCandidates or showLiqDebug) and str.length(z.liquidityRejectedReason) > 0" in source


def test_demand_own_origin_liquidity_can_seed_waiting_zone() -> None:
    for path in INDICATORS:
        source = path.read_text()

        assert "demandOwnOriginLiquidity(RawZone z)" in source
        assert "ownOriginLocal = not na(z.originBar) and pBar == z.originBar" in source
        assert "[ownOriginPrice, ownOriginBar, ownOriginDist] = demandOwnOriginLiquidity(out)" in source
        assert 'bestSource := "OWN_ORIGIN"' in source
        assert 'bestSource == "ORIGIN_HIGH_REFERENCE" or bestSource == "OWN_ORIGIN" ? true : demandLegCount >= minLegCandles' in source
        assert "SELECTED_OWN_ORIGIN" in source
        assert "bool ownOriginLiquidity = liquidityCandidateIsOwnOrigin(z, z.liquidityBarIndex, z.liquidityPrice)" in source
        assert "isInvalid := not ownOriginLiquidity and" in source


def test_zone_liquidity_distance_cap_scope_matches_reference_alignment() -> None:
    for path in INDICATORS:
        source = path.read_text()

        assert source.count("float maxDistPrice = na") >= 3
        assert source.count("float maxDistPrice = liquidityMaxDistancePrice()") == 2


def test_local_one_candle_liquidity_competes_with_pivot_candidates() -> None:
    for path in INDICATORS:
        source = path.read_text()

        assert "if na(bestLiqBar) and enableOneCandleLiquidity" not in source
        assert source.count("if enableOneCandleLiquidity") >= 2


def test_inactive_zone_debug_keeps_removed_zones_visible() -> None:
    for path in INDICATORS:
        source = path.read_text()

        assert 'showInactiveZoneDebug = input.bool(false, "Debug inactive zones"' in source
        assert "bool showZone = z.active or showInactiveZoneDebug" in source
        assert "if not z.active and showInactiveZoneDebug" in source
        assert "if not showInactiveZoneDebug\n                deleteZoneDrawings(out)" in source


def test_xau_supply_return_before_sweep_does_not_invalidate_zone() -> None:
    for path in INDICATORS:
        source = path.read_text()

        assert "bool returnedInvalidates = returnedBeforeSweep and not is_gold" in source
        assert "expiredByAge or returnedInvalidates or wickBreak" in source


def test_supply_bullish_wick_touch_invalidates_before_liquidity() -> None:
    for path in INDICATORS:
        source = path.read_text()

        assert "bool bullishWickTouchesSupplyFromBelow = canJudgeInvalidation and isBullish(0) and close < out.bottom and high >= out.bottom" in source
        assert "bool bullishWickTouchBeforeSweep = bullishWickTouchesSupplyFromBelow and not closeInsideZone" in source
        assert "bool touchSweepProofReady = proofReadyOnOrBeforeThisBar and out.liqSource == TOUCH_SWEEP_SOURCE" in source
        assert "if canJudgeInvalidation and afterCreated and (closeInsideZone or wicksIntoZone) and not out.liquiditySwept and not bullishWickTouchBeforeSweep" in source
        assert "bool supplyWickTouchInvalidates = bullishWickTouchBeforeSweep and (not proofReadyOnOrBeforeThisBar or touchSweepProofReady)" in source
        assert "or supplyWickTouchInvalidates" in source


def test_supply_inducement_uses_retracement_high_liquidity() -> None:
    for path in INDICATORS:
        source = path.read_text()

        assert "supplyOneCandleRetracementLiquidityAt(int offset)" in source
        assert "bool newerHighRejected = high[offset] >= high[offset - 1]" in source
        assert "bool retracementRescanAllowed = use_inducement_linking and enableOneCandleLiquidity and out.liqSource != \"RETRACEMENT\" and not out.liquiditySwept" in source
        assert "if not out.active or out.demand or ((out.liquidityValid or out.targetSwept) and not retracementRescanAllowed) or out.liquiditySwept" in source
        assert "if use_inducement_linking and enableOneCandleLiquidity" in source
        assert "bool bestIsRetracement = bestSource == \"RETRACEMENT\"" in source
        if path.name.endswith("_LAB.pine"):
            assert "sameSide and (not bestIsRetracement or isCloser or (isSameDistance and isEarlierPivot))" in source
        else:
            assert "sameSide and (not bestIsRetracement or isCloser or (isSameDistance and isMoreRecent))" in source
        assert "bestSource := \"RETRACEMENT\"" in source


def test_suppressed_symbol_supply_recovers_historical_origin_without_stacked_zone() -> None:
    for path in INDICATORS:
        source = path.read_text()

        assert "hasActiveSimilarSupplyZone(float top, float bottom)" in source
        assert "resolveHistoricalSuppressedStandardSupplyCandidateAt(int candidateBaseIdx)" in source
        assert "int departureIdx = candidateBaseIdx - 1 - departureWalk" in source
        assert "displacement_leg_confirmed(departureIdx, candidateBaseIdx, false)" in source
        assert "standardConfirmationCloseLeavesZone(departureIdx, candidateBaseIdx, false)" in source
        assert "close[historicalOffset] > top" in source
        assert "historicalSupplyMaxBaseIdx = math.min(maxZoneAgeBars, bar_index - 1)" in source
        assert "resolveHistoricalSuppressedStandardSupplyCandidateAt(historicalSupplyBaseIdx)" in source
        assert "historicalSupplyValid and historicalSupplyConfirmationIdx == 0" in source
        assert "createZone(historicalSupplyBaseIdx, false, nextZoneId, historicalSupplyLegCandles, MODEL_STANDARD, historicalSupplyConfirmationBar)" in source
        assert "historicalSupplyCreated := true" in source
        assert "stackedSupplyCreatedCount" not in source
        assert "createZone(stackedSupplyBaseIdx, false" not in source


def test_historical_supply_uses_first_departure_confirmation_not_current_bar_only() -> None:
    for path in INDICATORS:
        source = path.read_text()

        supply_start = source.index("resolveHistoricalSuppressedStandardSupplyCandidateAt(int candidateBaseIdx)")
        supply_end = source.index("resolveZoneCandidate(bool demand, bool continuationMode)", supply_start)
        supply_body = source[supply_start:supply_end]

        assert "bool hasDepartureConfirmation = not na(firstDepartureConfirmationIdx)" in supply_body
        assert "if hasDepartureConfirmation" in supply_body
        assert "candidateConfirmationIdx := firstDepartureConfirmationIdx" in supply_body
        assert "firstDepartureConfirmationIdx == 0" not in supply_body


def test_suppressed_symbol_supply_final_bounds_include_prior_bearish_wick() -> None:
    for path in INDICATORS:
        source = path.read_text()

        bounds_start = source.index("zoneBoundsForFinalModel(int baseIdx, bool demand, int legCandles, string model)")
        bounds_end = source.index("zoneBounds(int baseIdx, bool demand, int legCandles, bool includeFormationWicks)", bounds_start)
        bounds_body = source[bounds_start:bounds_end]

        assert "bool suppressSupplyFormationWicks = not demand and accSuppressedSymbol()" in bounds_body
        assert "if suppressSupplyFormationWicks" in bounds_body
        assert "int departureIdx = baseIdx - 1" in bounds_body
        assert "bool departureBearishWickAboveOrigin = departureIdx >= 0 and isBearish(departureIdx) and high[departureIdx] > top" in bounds_body
        assert "finalTop := departureBearishWickAboveOrigin ? high[departureIdx] : top" in bounds_body
        assert "finalBottom := bottom" in bounds_body
        assert "extendFormationWickBounds(baseIdx, demand, legCandles, true, top, bottom)" in bounds_body


def test_xau_supply_base_uses_bullish_origin_not_bearish_drop_candle() -> None:
    for path in INDICATORS:
        source = path.read_text()

        assert "supplyReversalBase" not in source
        assert "bool baseSide = demand ? isBearish(offset) : isBullish(offset)" in source


def test_zone_debug_marks_1605_supply_candidate_path() -> None:
    for path in INDICATORS:
        source = path.read_text()

        assert 'showZoneDebug = input.bool(false, "Debug zone detection"' in source
        assert 'hour(time[offset], "GMT+3") == 16' in source
        assert 'minute(time[offset], "GMT+3") == 5' in source
        assert 'drawZoneCandidateDebug(candidateBaseIdx, demand, candidateBaseValid, candidateValid, candidateRejectReason, candidateConfirmationIdx, "STANDARD")' in source
        assert 'drawZoneCandidateDebug(candidateBaseIdx, false, candidateBaseValid, candidateValid, candidateRejectReason, candidateConfirmationIdx, "HIST_SUPPLY")' in source
