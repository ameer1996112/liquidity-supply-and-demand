import re
from pathlib import Path


LAB = Path("scripts/pinescript/indicators/SND_RD_5M_V1_LAB.pine")


def source() -> str:
    return LAB.read_text(encoding="utf-8")


def test_new_lab_is_non_executable_and_close_confirmed() -> None:
    text = source()
    assert 'indicator("SND RD 5M V1 LAB"' in text
    assert "strategy(" not in text
    assert "strategy." not in text
    assert "barstate.isconfirmed and isFiveMinute" in text
    assert '"\\\"executable\\\":false,"' in text


def test_accuracy_geometry_uses_body_proximal_and_origin_wick_distal() -> None:
    text = source()
    assert "float bodyHigh = math.max(candidate.originOpen, candidate.originClose)" in text
    assert "float bodyLow = math.min(candidate.originOpen, candidate.originClose)" in text
    assert "float frozenTop = accuracy and demand ? bodyHigh : candidate.originHigh" in text
    assert "float frozenBottom = accuracy and not demand ? bodyLow : candidate.originLow" in text
    assert "candidate.originHigh > candidate.firstDepartureHigh" in text
    assert "candidate.originLow < candidate.firstDepartureLow" in text


def test_formation_wicks_extend_only_distal_boundary_before_confirmation() -> None:
    text = source()
    assert "na(this.distal) ? low : math.min(this.distal, low)" in text
    assert "na(this.distal) ? high : math.max(this.distal, high)" in text
    assert "this.distal := demand ? math.min(this.distal, low) : math.max(this.distal, high)" in text
    assert "frozenBottom := math.min(frozenBottom, candidate.distal)" in text
    assert "frozenTop := math.max(frozenTop, candidate.distal)" in text

    assert len(re.findall(r"zone\.top\s*:=", text)) == 1
    assert len(re.findall(r"zone\.bottom\s*:=", text)) == 1


def test_inside_base_interruption_restarts_formation_envelope() -> None:
    text = source()
    assert "method rebaseInsideFormation(Candidate this, bool demand)" in text
    assert "high <= this.originHigh and low >= this.originLow" in text
    assert "this.originBar := bar_index" in text
    assert "this.distal := demand ? low : high" in text
    assert "float rebasedDistal" not in text
    assert "bool rebasedSupply = supplyCandidate.rebaseInsideFormation(false)" in text
    assert "bool rebasedDemand = demandCandidate.rebaseInsideFormation(true)" in text


def test_reversal_and_continuation_are_independent_of_geometry() -> None:
    text = source()
    assert "FORMATION_REVERSAL" in text
    assert "FORMATION_CONTINUATION" in text
    assert "GEOMETRY_STANDARD" in text
    assert "GEOMETRY_ACCURACY" in text


def test_approach_classification_skips_intervening_dojis() -> None:
    text = source()
    assert "const int APPROACH_LOOKBACK_BARS = 20" in text
    assert "previousDirectionalCandle() =>" in text
    assert "for offset = 1 to APPROACH_LOOKBACK_BARS" in text
    assert text.count("this.approachDirection := previousDirectionalCandle()") == 2
    assert "bool continuation = demand ? candidate.approachDirection == 1" in text


def test_zone_identity_and_lifecycle_are_deterministic() -> None:
    text = source()
    assert "zone.originTime := candidate.originTime" in text
    assert "zone.confirmationTime := time_close" in text
    assert "zone.state := STATE_FRESH" in text
    assert "bar_index > zone.confirmationBar" in text
    assert "TAP_POST_CONFIRM_OVERLAP" in text
    assert "INVALIDATE_CLOSE_BEYOND_DISTAL" in text
    assert "REJECT_FORMATION_INTERRUPTED" in text


def test_same_direction_departure_wicks_do_not_tap_confirmed_zone() -> None:
    text = source()
    assert "zone.departureActive := true" in text
    assert "bool sameDirectionDeparture = zone.demand ? close > open : close < open" in text
    assert "zone.departureActive and sameDirectionDeparture" in text
    assert "zone.departureActive := false" in text


def test_detector_has_no_legacy_threshold_or_symbol_overrides() -> None:
    text = source()
    assert "ta.atr" not in text
    assert "syminfo.ticker" not in text.replace("syminfo.tickerid", "")
    assert "formationLegScanBars" not in text
    assert "enableContinuationZones" not in text
    assert "SND_Raw_RD_Forex" not in text


def test_object_budgets_stay_below_tradingview_limits() -> None:
    text = source()
    header = text.split("\n", 1)[1]
    for field in ("max_boxes_count", "max_labels_count"):
        match = re.search(rf"{field}\s*=\s*(\d+)", header)
        assert match is not None
        assert int(match.group(1)) <= 300
    line_match = re.search(r"max_lines_count\s*=\s*(\d+)", header)
    assert line_match is not None
    assert int(line_match.group(1)) <= 500
    assert 'maxZones = input.int(120, "Maximum zones", minval = 10, maxval = 200' in text


def test_liquidity_eligibility_matches_reference_detector_contract() -> None:
    text = source()
    assert 'ELIGIBILITY_WAITING = "WAITING_FOR_LIQUIDITY"' in text
    assert 'ELIGIBILITY_ELIGIBLE = "ELIGIBLE"' in text
    assert 'ELIGIBILITY_EXPIRED = "EXPIRED"' in text
    assert "run.count >= 2" in text
    assert "math.max(high[1], high)" in text
    assert "math.min(low[1], low)" in text
    assert "level.demand ? high > level.anchor : low < level.anchor" in text
    assert "candidate.runStartBar > zone.confirmationBar" in text
    assert "candidate.nearExtreme > zone.top" in text
    assert "candidate.nearExtreme < zone.bottom" in text
    assert "zone.eligibilityReason := EXPIRE_ZONE_NOT_FRESH" in text


def test_raw_audit_visibility_is_independent_from_strategy_eligibility() -> None:
    text = source()
    visible_body = text.split(
        "zoneVisible(RawZone zone, array<RawZone> allZones) =>", 1
    )[1].split(
        "zoneColor(RawZone zone) =>", 1
    )[0]
    assert "lifecycleVisible" in visible_body
    visibility_line = next(
        line for line in visible_body.splitlines() if "DISPLAY_RAW_AUDIT ?" in line
    )
    raw_branch = visibility_line.split("DISPLAY_RAW_AUDIT ?", 1)[1].split(":", 1)[0]
    assert "lifecycleVisible" in raw_branch
    assert "eligibility" not in raw_branch.lower()


def test_closest_completed_liquidity_is_the_primary_candidate() -> None:
    text = source()
    assert "type LiquidityLevel" in text
    assert "array<LiquidityLevel> levels" in text
    assert "array<int> createdIndexes" in text
    assert "candidate.nearExtreme <= primary.nearExtreme" in text
    assert "candidate.nearExtreme >= primary.nearExtreme" in text
    assert "string nextEligibility = primary.taken ? ELIGIBILITY_ELIGIBLE : ELIGIBILITY_WAITING" in text
    assert "zone.eligibilityState := nextEligibility" in text
    assert "bool primaryChanged = na(zone.liquidityAnchor)" in text
    assert "if primaryChanged or stateChanged" in text


def test_liquidity_lines_preserve_anchor_and_sweep_provenance() -> None:
    text = source()
    assert "int anchorBar" in text
    assert "int nearExtremeBar" in text
    assert "int runStartBar" in text
    assert "int formedBar" in text
    assert "int takenBar" in text
    assert "run.anchorBar := priorIsAnchor ? bar_index - 1 : bar_index" in text
    assert "run.nearExtremeBar := bar_index" in text
    assert "level.formedBar := bar_index - 1" in text
    assert "level.takenBar := bar_index" in text


def test_liquidity_line_renderer_draws_all_zone_relative_levels() -> None:
    text = source()
    assert 'showLiquidityLines = input.bool(true, "Show liquidity lines"' in text
    assert "if zoneVisible(zone, allZones)" in text
    assert "array<int> liquidityIndexes" in text
    assert "zone.liquidityIndexes := array.new<int>()" in text
    assert "addUniqueLiquidityIndex(zone.liquidityIndexes, candidateIndex)" in text
    assert "int linkedCount = array.size(zone.liquidityIndexes)" in text
    assert "array.get(zone.liquidityIndexes, linkedOffset)" in text
    assert "candidate.runStartBar > zone.confirmationBar" in text
    assert "candidate.nearExtreme > zone.top" in text
    assert "candidate.nearExtreme < zone.bottom" in text
    assert "rawAuditLiquidityLevels" not in text
    assert "nearestDemandIndex" not in text
    assert "nearestSupplyIndex" not in text
    assert "int rightBar = bar_index + projectionBars" in text
    assert "level.taken ? level.takenBar" not in text
    assert "line.style_dashed" in text
    assert "line.style_solid" in text
    assert "line.style_dotted" in text
    assert "line.new(level.nearExtremeBar, level.nearExtreme" in text
    assert "line.new(level.anchorBar, level.anchor" in text
    assert "if not premiumVisuals and displayMode == DISPLAY_RAW_AUDIT" in text
    assert "updateLiquidityDrawings(liquidityLevels, drawnLiquidityIndexes, zones)" in text
    assert "line.delete(previousLevel.liquidityLine)" in text
    assert "line.delete(previousLevel.ownExtremeLine)" in text


def test_premium_visuals_are_clean_by_default_without_changing_detection() -> None:
    text = source()
    assert 'premiumVisuals = input.bool(true, "Premium visuals"' in text
    assert 'showStatusPanel = input.bool(false, "Show status panel"' in text
    assert "premiumVisuals ? color.new(baseColor, 76) : baseColor" in text
    assert "premiumVisuals ? 1 : zone.geometry == GEOMETRY_ACCURACY ? 2 : 1" in text
    assert "box.set_border_width(zone.zoneBox, zoneBorderWidth(zone))" in text
    assert "not premiumVisuals and displayMode == DISPLAY_RAW_AUDIT and showLabels" in text
    assert "premiumVisuals ? color.new(color.gray, level.taken ? 40 : 10)" in text
    assert "string lineStyle = level.taken ? line.style_solid : line.style_dashed" in text
    assert "int lineWidth = primary ? 2 : 1" in text
    assert "if not premiumVisuals and displayMode == DISPLAY_RAW_AUDIT" in text
    assert "if showStatusPanel" in text
    assert 'premiumVisuals ? "" : lastDecision' in text

    decision_body = text.split(
        "if barstate.isconfirmed and isFiveMinute", 1
    )[1].split("int drawCount", 1)[0]
    assert "premiumVisuals" not in decision_body
    assert "showStatusPanel" not in decision_body


def test_global_liquidity_runs_are_bidirectional_and_zone_independent() -> None:
    text = source()
    assert "var LiquidityRun demandLiquidityRun" in text
    assert "var LiquidityRun supplyLiquidityRun" in text
    assert "var LiquidityLevel[] liquidityLevels" in text
    assert "extendLiquidityRun(demandRun, true)" in text
    assert "extendLiquidityRun(supplyRun, false)" in text
    assert "completeLiquidityRun(supplyRun, false" in text
    assert "completeLiquidityRun(demandRun, true" in text
    assert "oneCandleEvent.startBar := run.startBar" in text
    assert "demandOneCandleEvent.startBar > zone.confirmationBar" in text
    assert "supplyOneCandleEvent.startBar > zone.confirmationBar" in text
    main = text.split("if barstate.isconfirmed and isFiveMinute", 1)[1]
    assert main.index("updateGlobalLiquidity(") < main.index("int zoneCount = array.size(zones)")


def test_opposite_zone_route_blocker_expires_only_strategy_eligibility() -> None:
    text = source()
    assert 'EXPIRE_OPPOSITE_ZONE_RETRACE = "EXPIRE_OPPOSITE_ZONE_RETRACE"' in text
    assert "int routeBlockerId" in text
    assert "routeBlockerId(RawZone target, array<RawZone> allZones) =>" in text
    assert "candidate.state == STATE_TAPPED and candidate.stateBar == bar_index" in text
    assert "candidate.bottom > target.top" in text
    assert "candidate.top < target.bottom" in text
    assert "zone.eligibilityState := ELIGIBILITY_EXPIRED" in text
    assert "zone.eligibilityReason := EXPIRE_OPPOSITE_ZONE_RETRACE" in text
    assert "zone.routeBlockerId := blockerId" in text

    visible_body = text.split(
        "zoneVisible(RawZone zone, array<RawZone> allZones) =>", 1
    )[1].split(
        "zoneColor(RawZone zone) =>", 1
    )[0]
    assert "routeBlocker" not in visible_body


def test_setup_handoff_tracks_first_valid_return_without_executing() -> None:
    text = source()
    assert 'SETUP_WAITING = "WAITING_FOR_ELIGIBILITY"' in text
    assert 'SETUP_ARMED = "ARMED"' in text
    assert 'SETUP_TRIGGERED = "TRIGGERED"' in text
    assert 'SETUP_REJECTED = "REJECTED"' in text
    assert "updateSetupState(RawZone zone, array<RawZone> allZones) =>" in text
    assert "transitionSetup(zone, SETUP_ARMED, ARM_SETUP_AFTER_LIQUIDITY)" in text
    assert (
        "transitionSetup(zone, SETUP_TRIGGERED, "
        "TRIGGER_FIRST_FRESH_TAP_AFTER_LIQUIDITY)" in text
    )
    assert (
        "transitionSetup(zone, SETUP_REJECTED, "
        "REJECT_TARGET_TAP_WITHOUT_ELIGIBILITY)" in text
    )
    assert (
        "transitionSetup(zone, SETUP_REJECTED, "
        "REJECT_TARGET_INVALIDATED_ON_RETURN)" in text
    )
    assert '"\\\"setup_state\\\":\\\"" + zone.setupState' in text
    assert '"\\\"setup_reason\\\":\\\"" + zone.setupReason' in text
    assert "strategy(" not in text
    assert "strategy." not in text


def test_same_bar_route_ambiguity_fails_closed() -> None:
    text = source()
    assert "sameBarRouteBlockerId(RawZone target, array<RawZone> allZones) =>" in text
    assert "target.state == STATE_TAPPED and target.stateBar == bar_index" in text
    assert "bar_index > target.eligibilityBar" in text
    assert "zone.eligibilityState := ELIGIBILITY_EXPIRED" in text
    assert "REJECT_AMBIGUOUS_SAME_BAR_ROUTE" in text


def test_setup_state_does_not_control_raw_audit_visibility() -> None:
    text = source()
    visible_body = text.split(
        "zoneVisible(RawZone zone, array<RawZone> allZones) =>", 1
    )[1].split(
        "zoneColor(RawZone zone) =>", 1
    )[0]
    visibility_line = next(
        line for line in visible_body.splitlines() if "DISPLAY_RAW_AUDIT ?" in line
    )
    raw_branch = visibility_line.split("DISPLAY_RAW_AUDIT ?", 1)[1].split(":", 1)[0]
    assert "setup" not in raw_branch.lower()


def test_clean_view_shows_fresh_zones_and_qualified_only_is_explicit() -> None:
    text = source()
    assert 'DISPLAY_CLEAN = "Clean"' in text
    assert 'DISPLAY_QUALIFIED_ONLY = "Qualified only"' in text
    assert 'DISPLAY_RAW_AUDIT = "Raw audit"' in text
    assert 'displayMode = input.string(DISPLAY_CLEAN, "View"' in text
    assert "options = [DISPLAY_CLEAN, DISPLAY_QUALIFIED_ONLY, DISPLAY_RAW_AUDIT]" in text
    assert 'cleanZonesPerLevel = input.int(1, "Clean zones per overlapping level"' in text
    assert 'showTapped = input.bool(false, "Show tapped zones"' in text
    assert "zonesOverlap(RawZone first, RawZone other) =>" in text
    assert "first.bottom <= other.top and first.top >= other.bottom" in text
    assert "bool liquidityQualified" in text
    assert "zone.liquidityQualified := false" in text
    assert "zone.liquidityQualified := true" in text
    assert "zoneIncludedInCuratedView(RawZone zone) =>" in text
    assert "zone.state == STATE_FRESH" in text
    assert "displayMode != DISPLAY_QUALIFIED_ONLY or zone.liquidityQualified" in text
    assert "zoneSelectedForCleanView(RawZone target, array<RawZone> allZones) =>" in text
    assert "candidate.demand == target.demand" in text
    assert "zoneIncludedInCuratedView(candidate)" in text
    assert "zonesOverlap(candidate, target)" in text
    assert "closerCount < cleanZonesPerLevel" in text
    assert "showFresh and zoneIncludedInCuratedView(zone)" in text

    decision_body = text.split(
        "if barstate.isconfirmed and isFiveMinute", 1
    )[1].split("int drawCount", 1)[0]
    assert "displayMode" not in decision_body
    assert "cleanZonesPerLevel" not in decision_body


def test_diagnostic_labels_expose_frozen_geometry_provenance() -> None:
    text = source()
    for field in (
        "originHigh",
        "originLow",
        "firstDepartureHigh",
        "firstDepartureLow",
        "formationDistal",
    ):
        assert f"zone.{field} := candidate.{field.replace('formationDistal', 'distal')}" in text
    assert 'string bounds = "oH "' in text
    assert 'str.tostring(zone.top, format.mintick)' in text
    assert 'str.tostring(zone.bottom, format.mintick)' in text
