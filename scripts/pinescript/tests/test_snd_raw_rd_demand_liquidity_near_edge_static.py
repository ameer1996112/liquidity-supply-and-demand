from pathlib import Path


INDICATORS = [
    Path("scripts/pinescript/indicators/SND_Raw_RD_Forex.pine"),
    Path("scripts/pinescript/indicators/SND_Raw_RD_Forex_PROD.pine"),
]

LAB = Path("scripts/pinescript/indicators/SND_Raw_RD_Forex_LAB.pine")


def _function_body(source: str, name: str, next_name: str) -> str:
    start = source.index(f"{name}(")
    end = source.index(f"\n{next_name}(", start)
    return source[start:end]


def test_demand_liquidity_prefers_non_edge_inducement_candidates() -> None:
    for path in INDICATORS:
        body = _function_body(path.read_text(), "f_scan_demand_liquidity", "f_scan_supply_liquidity")

        assert "bool bestLiqNearEdge = false" in body
        assert "float zoneHeight = math.abs(out.top - out.bottom)" in body
        assert "bool preferAwayFromEdge = use_inducement_linking and zoneHeight >= pip_size * 5.0" in body
        assert "bool isNearEdge = preferAwayFromEdge and distFromZone < pip_size * 2.0" in body
        assert "bool improvesEdgeQuality = bestLiqNearEdge and not isNearEdge" in body
        assert "bool sameEdgeQuality = bestLiqNearEdge == isNearEdge" in body
        assert "if na(bestLiqBar) or improvesEdgeQuality or (sameEdgeQuality and (isCloser or (isSameDistance and isMoreRecent)))" in body
        assert body.count("bestLiqNearEdge := isNearEdge") == 3


def test_supply_liquidity_ranking_remains_reference_strategy_closest_first() -> None:
    for path in INDICATORS:
        body = _function_body(path.read_text(), "f_scan_supply_liquidity", "clearStrategyLiquidityState")

        assert "bestLiqNearEdge" not in body
        assert "preferAwayFromEdge" not in body


def test_lab_liquidity_tie_break_is_closest_edge_then_earliest_pivot() -> None:
    source = LAB.read_text()
    demand_body = _function_body(source, "f_scan_demand_liquidity", "f_scan_supply_liquidity")
    supply_body = _function_body(source, "f_scan_supply_liquidity", "clearStrategyLiquidityState")

    assert "bool isEarlierPivot = na(bestLiqBar) or pBar < bestLiqBar" in demand_body
    assert "bool isEarlierPivot = na(bestLiqBar) or pBar < bestLiqBar" in supply_body
    assert "isSameDistance and isEarlierPivot" in demand_body
    assert "isSameDistance and isEarlierPivot" in supply_body


def test_lab_debug_alerts_are_allowlisted_and_never_executable() -> None:
    source = LAB.read_text()
    send_event = _function_body(source, "sendEvent", "sameBounds")

    assert "isLabDebugEvent(string eventName)" in source
    assert 'eventName == "ZONE_CANDIDATE"' in source
    assert 'eventName == "ZONE_CONFIRMED_NON_EXECUTABLE"' in source
    assert 'eventName == "LIQUIDITY_LINKED"' in source
    assert 'eventName == "LIQUIDITY_SWEPT"' in source
    assert 'eventName == "TARGET_SWEPT"' in source
    assert 'eventName == "ZONE_TOUCHED"' in source
    assert 'eventName == "ZONE_INVALIDATED"' in source
    assert 'eventName == "TRADE_ELIGIBLE_EXECUTABLE"' not in source
    assert "if isLabDebugEvent(eventName)" in send_event
    assert "alert(payload(eventName, z), alert.freq_once_per_bar_close)" in send_event


def test_lab_confirmation_debug_alert_only_for_current_bar_confirmation() -> None:
    source = LAB.read_text()
    create_zone = _function_body(source, "createZone", "hideInactiveZone")

    assert 'if confirmationBar == bar_index\n                    sendEvent("ZONE_CONFIRMED_NON_EXECUTABLE", z)' in create_zone
