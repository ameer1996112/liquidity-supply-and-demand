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


def test_inside_base_interruption_rebases_and_keeps_formation_envelope() -> None:
    text = source()
    assert "method rebaseInsideFormation(Candidate this, bool demand)" in text
    assert "high <= this.originHigh and low >= this.originLow" in text
    assert "float rebasedDistal = demand ? math.min(this.distal, low) : math.max(this.distal, high)" in text
    assert "this.originBar := bar_index" in text
    assert "this.distal := rebasedDistal" in text
    assert "bool rebasedSupply = supplyCandidate.rebaseInsideFormation(false)" in text
    assert "bool rebasedDemand = demandCandidate.rebaseInsideFormation(true)" in text


def test_reversal_and_continuation_are_independent_of_geometry() -> None:
    text = source()
    assert "FORMATION_REVERSAL" in text
    assert "FORMATION_CONTINUATION" in text
    assert "GEOMETRY_STANDARD" in text
    assert "GEOMETRY_ACCURACY" in text
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
    assert 'maxZones = input.int(120, "Maximum zones", minval = 10, maxval = 200' in text


def test_liquidity_eligibility_matches_reference_detector_contract() -> None:
    text = source()
    assert 'ELIGIBILITY_WAITING = "WAITING_FOR_LIQUIDITY"' in text
    assert 'ELIGIBILITY_ELIGIBLE = "ELIGIBLE"' in text
    assert 'ELIGIBILITY_EXPIRED = "EXPIRED"' in text
    assert "zone.liquidityRunCount >= 2" in text
    assert "math.max(high[1], high)" in text
    assert "math.min(low[1], low)" in text
    assert "high > candidateAnchor" in text
    assert "low < candidateAnchor" in text
    assert "zone.eligibilityReason := EXPIRE_ZONE_NOT_FRESH" in text


def test_liquidity_eligibility_never_hides_raw_zones() -> None:
    text = source()
    visible_body = text.split(
        "zoneVisible(RawZone zone, array<RawZone> allZones) =>", 1
    )[1].split(
        "zoneColor(RawZone zone) =>", 1
    )[0]
    assert "zone.state" in visible_body
    assert "eligibility" not in visible_body.lower()


def test_closest_completed_liquidity_is_the_primary_candidate() -> None:
    text = source()
    assert "array<float> liquidityExtremes" in text
    assert "array<bool> liquidityTaken" in text
    assert "zone.liquidityRunNearExtreme" in text
    assert "float candidateExtreme = array.get(zone.liquidityExtremes" in text
    assert "candidateExtreme <= primaryExtreme" in text
    assert "candidateExtreme >= primaryExtreme" in text
    assert "bool primaryTaken = array.get(zone.liquidityTaken, primaryIndex)" in text
    assert "string nextEligibility = primaryTaken ? ELIGIBILITY_ELIGIBLE : ELIGIBILITY_WAITING" in text
    assert "zone.eligibilityState := nextEligibility" in text
    assert "bool primaryChanged = na(previousPrimaryIndex)" in text
    assert "if primaryChanged or stateChanged" in text


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


def test_setup_state_does_not_control_raw_zone_visibility() -> None:
    text = source()
    visible_body = text.split(
        "zoneVisible(RawZone zone, array<RawZone> allZones) =>", 1
    )[1].split(
        "zoneColor(RawZone zone) =>", 1
    )[0]
    assert "setup" not in visible_body.lower()


def test_clean_view_limits_visible_raw_zones_without_changing_detection() -> None:
    text = source()
    assert 'DISPLAY_CLEAN = "Clean"' in text
    assert 'DISPLAY_RAW_AUDIT = "Raw audit"' in text
    assert 'displayMode = input.string(DISPLAY_CLEAN, "View"' in text
    assert 'cleanZonesPerSide = input.int(3, "Clean zones per side"' in text
    assert 'showTapped = input.bool(false, "Show tapped zones"' in text
    assert "zoneSelectedForCleanView(RawZone target, array<RawZone> allZones) =>" in text
    assert "candidate.demand == target.demand" in text
    assert "candidate.state == STATE_FRESH" in text
    assert "closerCount < cleanZonesPerSide" in text

    decision_body = text.split(
        "if barstate.isconfirmed and isFiveMinute", 1
    )[1].split("int drawCount", 1)[0]
    assert "displayMode" not in decision_body
    assert "cleanZonesPerSide" not in decision_body
