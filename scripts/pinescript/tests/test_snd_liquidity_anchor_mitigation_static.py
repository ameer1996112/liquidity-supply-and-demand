from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
STRATEGY = ROOT / "scripts/pinescript/strategies/SND_Strategy.pine"


def _body(source: str, start_marker: str, end_marker: str) -> str:
    if start_marker not in source:
        return ""
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[start:end]


def main() -> None:
    strategy = STRATEGY.read_text(encoding="utf-8")
    demand_scan = _body(strategy, "f_scan_demand_liquidity", "\nf_scan_supply_liquidity")
    supply_scan = _body(strategy, "f_scan_supply_liquidity", "\nf_check_demand_sweeps")
    visual_block = _body(strategy, "zone_is_live(Core.Zone z) =>", "\nzone_overlap_pct")

    required = [
        "zone_is_live(Core.Zone z) =>",
        "z.active and not z.mitigated and na(z.lastEntryBar)",
        "zone_is_overlap_visually_hidden(Core.Zone z) =>",
        'zone_inactive_reason(z) == "OVERLAP_VISUALLY_HIDDEN"',
        "not zone_is_used_or_mitigated(z) and not zone_is_overlap_visually_hidden(z)",
        "bool archiveDisplayZone = show_mitigated_zones and usedOrMitigated",
        "bool activeDisplayZone = zone_is_live(z) and not invalidOrRejected and not overlapHidden",
        "if zone_is_live(z)",
        'z.inactiveReason := "MITIGATED"',
        "hideOverlappingDemandZones(z.top, z.bottom)",
        "hideOverlappingSupplyZones(z.top, z.bottom)",
        'z.inactiveReason := "OVERLAP_VISUALLY_HIDDEN"',
        "array.set(demandZones, idx, z)",
        "array.set(supplyZones, idx, z)",
        "REJECT_LIQ_INSIDE_ZONE",
        "REJECT_LIQ_TOO_FAR",
        "REJECT_LIQ_PIVOT_INVALID",
        "REJECT_LIQ_NOT_STRONG",
        "var line[] rejectedLiqDebugLines = array.new_line()",
        "var label[] rejectedLiqDebugLabels = array.new_label()",
        "addRejectedLiquidityDebugLine(",
        "barstate.islast",
        "bool should_scan_demand_this_bar = isPvtLow or na(z.liqSource)",
        "if should_rescan_demand_liq and should_scan_demand_this_bar",
        "bool should_scan_supply_this_bar = isPvtHigh or na(z.liqSource)",
        "if should_rescan_supply_liq and should_scan_supply_this_bar",
        "if barstate.islast",
        "z.liqSource := liqRejectReason",
    ]

    for needle in required:
        if needle not in strategy:
            raise AssertionError(f"Missing liquidity/mitigation contract marker: {needle}")

    demand_required = [
        "float bestDist = 1.0e10",
        "bool isValidLocation = pLow > z.top",
        "float distFromZone = pLow - z.top",
        'liqRejectReason := "REJECT_LIQ_INSIDE_ZONE"',
        'liqRejectReason := "REJECT_LIQ_TOO_FAR"',
        'liqRejectReason := "REJECT_LIQ_PIVOT_INVALID"',
        "bool isSameDistance = math.abs(distFromZone - bestDist) <= syminfo.mintick",
        "bool isMoreRecent = na(bestLiqBar) or pBar > bestLiqBar",
        "if na(bestLiqBar) or distFromZone < bestDist or (isSameDistance and isMoreRecent)",
        "bestDist := distFromZone",
        "rejectedDebugPrice := pLow",
        "rejectedDebugBar := pBar",
        "addRejectedLiquidityDebugLine(z.createdBarIndex, z.top, rejectedDebugBar, rejectedDebugPrice, liqRejectReason, true)",
        'z.liqSource := hasStrongLeg ? "MAKUCHAKU_PIVOT" : "REJECT_LIQ_NOT_STRONG"',
        "z.inactiveReason := na",
    ]

    for needle in demand_required:
        if needle not in demand_scan:
            raise AssertionError(f"Demand liquidity scan missing: {needle}")

    supply_required = [
        "float bestDist = 1.0e10",
        "bool isValidLocation = pHigh < z.bottom",
        "float distFromZone = z.bottom - pHigh",
        'liqRejectReason := "REJECT_LIQ_INSIDE_ZONE"',
        'liqRejectReason := "REJECT_LIQ_TOO_FAR"',
        'liqRejectReason := "REJECT_LIQ_PIVOT_INVALID"',
        "bool isSameDistance = math.abs(distFromZone - bestDist) <= syminfo.mintick",
        "bool isMoreRecent = na(bestLiqBar) or pBar > bestLiqBar",
        "if na(bestLiqBar) or distFromZone < bestDist or (isSameDistance and isMoreRecent)",
        "bestDist := distFromZone",
        "rejectedDebugPrice := pHigh",
        "rejectedDebugBar := pBar",
        "addRejectedLiquidityDebugLine(z.createdBarIndex, z.bottom, rejectedDebugBar, rejectedDebugPrice, liqRejectReason, false)",
        'z.liqSource := hasStrongLeg ? "MAKUCHAKU_PIVOT" : "REJECT_LIQ_NOT_STRONG"',
        "z.inactiveReason := na",
    ]

    for needle in supply_required:
        if needle not in supply_scan:
            raise AssertionError(f"Supply liquidity scan missing: {needle}")

    forbidden = [
        "if pLow < bestLiqPrice",
        "if pHigh > bestLiqPrice",
        "deactivateOverlappingDemandZones",
        "deactivateOverlappingSupplyZones",
        "deactivateDemandZone",
        "deactivateSupplyZone",
    ]

    for needle in forbidden:
        if needle in strategy:
            raise AssertionError(f"Contract forbids stale liquidity/display behavior: {needle}")

    if 'z.active := false' in visual_block:
        raise AssertionError("Visual/display block must not deactivate zones")

    print("SND liquidity anchor and mitigation static contract passed")


if __name__ == "__main__":
    main()
