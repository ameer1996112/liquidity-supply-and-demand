from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
STRATEGIES = [
    ROOT / "scripts/pinescript/strategies/SND_Strategy.pine",
    ROOT / "scripts/pinescript/strategies/SND_Strategey_refactor.pine",
]


def _body(source: str, start_marker: str, end_marker: str) -> str:
    if start_marker not in source:
        return ""
    start = source.index(start_marker)
    if end_marker not in source[start:]:
        return source[start:]
    end = source.index(end_marker, start)
    return source[start:end]


def main() -> None:
    for path in STRATEGIES:
        strategy = path.read_text(encoding="utf-8")

        demand_helper = _body(
            strategy,
            "invalidateDemandZone(int idx, string reason) =>",
            "invalidateSupplyZone(int idx, string reason) =>",
        )
        for needle in [
            "clearDemandLiquidityVisual(idx)",
            "z.active := false",
            "z.mitigated := true",
            "z.primed := false",
            "z.inactiveReason := reason",
            "apply_zone_visual(z, true)",
            "array.set(demandZones, idx, z)",
            "db_markInactive(z.id, reason)",
        ]:
            if needle not in demand_helper:
                raise AssertionError(f"{path.name}: demand invalidation missing {needle!r}")

        supply_helper = _body(
            strategy,
            "invalidateSupplyZone(int idx, string reason) =>",
            "isLiquidityValidForEntry(isDemand, idx) =>",
        )
        for needle in [
            "clearSupplyLiquidityVisual(idx)",
            "z.active := false",
            "z.mitigated := true",
            "z.primed := false",
            "z.inactiveReason := reason",
            "apply_zone_visual(z, false)",
            "array.set(supplyZones, idx, z)",
            "db_markInactive(z.id, reason)",
        ]:
            if needle not in supply_helper:
                raise AssertionError(f"{path.name}: supply invalidation missing {needle!r}")

        demand_lifecycle = _body(
            strategy,
            "int demandLifecycleSize = array.size(demandZones)",
            "int supplyLifecycleSize = array.size(supplyZones)",
        )
        for needle in [
            "if demandLifecycleSize > 0 and barstate.isconfirmed",
            "for i = 0 to demandLifecycleSize - 1",
            "bool proofReady = z.liquidityValid and z.liquiditySwept and z.targetSwept",
            "bool touchesDemand = low <= z.top and high >= z.bottom",
            "bool justLeftZoneThisBar = false",
            "if is_future_bar and z.leftZone and not justLeftZoneThisBar and touchesDemand and not proofReady",
            'invalidateDemandZone(i, "SETUP_INVALID_RETURN_BEFORE_PROOF")',
        ]:
            if needle not in demand_lifecycle:
                raise AssertionError(f"{path.name}: demand pre-proof return missing {needle!r}")
        if 'invalidateDemandZone(i, "ENTRY_BLOCKED:RETURN_BEFORE_PROOF")' in demand_lifecycle:
            raise AssertionError(f"{path.name}: demand pre-sweep return must fully invalidate")
        if "cached_demand_size" in demand_lifecycle:
            raise AssertionError(f"{path.name}: demand lifecycle must use current demandZones size after creation")

        supply_lifecycle = _body(
            strategy,
            "int supplyLifecycleSize = array.size(supplyZones)",
            "int demandSize = array.size(demandZones)",
        )
        for needle in [
            "if supplyLifecycleSize > 0 and barstate.isconfirmed",
            "for i = 0 to supplyLifecycleSize - 1",
            "bool proofReady = z.liquidityValid and z.liquiditySwept and z.targetSwept",
            "bool touchesSupply = high >= z.bottom and low <= z.top",
            "bool justLeftZoneThisBar = false",
            "if is_future_bar and z.leftZone and not justLeftZoneThisBar and touchesSupply and not proofReady",
            'invalidateSupplyZone(i, "SETUP_INVALID_RETURN_BEFORE_PROOF")',
        ]:
            if needle not in supply_lifecycle:
                raise AssertionError(f"{path.name}: supply pre-proof return missing {needle!r}")
        if 'invalidateSupplyZone(i, "ENTRY_BLOCKED:RETURN_BEFORE_PROOF")' in supply_lifecycle:
            raise AssertionError(f"{path.name}: supply pre-sweep return must use setup invalid reason")
        if "cached_supply_size" in supply_lifecycle:
            raise AssertionError(f"{path.name}: supply lifecycle must use current supplyZones size after creation")

        for needle in [
            "zone_invalidated_after_creation(float zTop, float zBottom, int baseIdx, bool isDemand) =>",
            "bool breaksDemand = isDemand and (low[idx] < zBottom or close[idx] < zBottom)",
            "bool breaksSupply = not isDemand and (high[idx] > zTop or close[idx] > zTop)",
            "bool historicallyInvalid = isHistorical and zone_invalidated_after_creation(zTop, zBottom, baseIdx, isDemand)",
            "if not historicallyInvalid and not skipDuplicateZone",
            "if is_future_bar and closesBelowDemand",
            "else if is_future_bar and wicksBelowDemand",
            "if is_future_bar and closesAboveSupply",
            "else if is_future_bar and wicksAboveSupply",
            "bool closesBelowDemand = close < z.bottom",
            "bool wicksBelowDemand = low < z.bottom",
            "bool closesAboveSupply = close > z.top",
            "bool wicksAboveSupply = high > z.top",
            'invalidateDemandZone(i, "SETUP_INVALID_CLOSE_BELOW_ZONE")',
            'invalidateSupplyZone(i, "SETUP_INVALID_CLOSE_ABOVE_ZONE")',
            'invalidateDemandZone(i, "SETUP_INVALID_WICK_BELOW_ZONE")',
            'invalidateSupplyZone(i, "SETUP_INVALID_WICK_ABOVE_ZONE")',
            'invalidateDemandZone(i, "SETUP_INVALID_ZONE_TOO_OLD")',
            'invalidateSupplyZone(i, "SETUP_INVALID_ZONE_TOO_OLD")',
        ]:
            if needle not in strategy:
                raise AssertionError(f"{path.name}: distal structural invalidation contract missing {needle!r}")
        for needle in [
            "if close_inside_demand or close_below_zone or isTooOld or (invalidate_on_wick and wick_below_zone)",
            "if close_inside_supply or close_above_zone or isTooOld or (invalidate_on_wick and wick_above_zone)",
            'invalidateDemandZone(i, "SETUP_INVALID_CLOSE_INSIDE_ZONE")',
            'invalidateSupplyZone(i, "SETUP_INVALID_CLOSE_INSIDE_ZONE")',
            "if is_future_bar and z.leftZone and not justLeftZoneThisBar and closesBelowDemand",
            "if is_future_bar and z.leftZone and not justLeftZoneThisBar and closesAboveSupply",
            "not justLeftZoneThisBar and closesBelowDemand",
            "not justLeftZoneThisBar and wicksBelowDemand",
            "not justLeftZoneThisBar and closesAboveSupply",
            "not justLeftZoneThisBar and wicksAboveSupply",
            "not justLeftZoneThisBar and closesBelowDemand and not proofReady",
            "not justLeftZoneThisBar and wicksBelowDemand and not proofReady",
            "not justLeftZoneThisBar and closesAboveSupply and not proofReady",
            "not justLeftZoneThisBar and wicksAboveSupply and not proofReady",
            "bool leftZone = false",
            "remove_zone_all_arrays(true, i)",
            "remove_zone_all_arrays(false, i)",
        ]:
            if needle in strategy:
                raise AssertionError(f"{path.name}: structural invalidation must use invalidate helpers, not removal: {needle!r}")

        for label, lifecycle in [
            ("demand", demand_lifecycle),
            ("supply", supply_lifecycle),
        ]:
            if "if z.isHistorical\n                continue" in lifecycle:
                raise AssertionError(f"{path.name}: {label} historical zones must still run invalidation lifecycle")

        create_zone = _body(
            strategy,
            "createZone(int baseIdx, bool isDemand, bool isHistorical, int candlesInBase, int legCandles, int zoneUZID, bool allowDepartureWickExtension) =>",
            "\nremove_zone_all_arrays(",
        )
        if not create_zone:
            raise AssertionError(f"{path.name}: createZone must use the current replay-safe signature")
        acceptance_gate = create_zone.index("if not historicallyInvalid and not skipDuplicateZone")
        demand_db = create_zone.index('db_upsertZone(z, "DEMAND")')
        demand_base_used = create_zone.index("array.push(used_demand_base_times, baseTime)")
        demand_created = create_zone.index("created := true", demand_db)
        if not (acceptance_gate < demand_db < demand_base_used < demand_created):
            raise AssertionError(f"{path.name}: demand base time must be reserved only after accepted zone creation")

        supply_db = create_zone.index('db_upsertZone(z, "SUPPLY")')
        supply_base_used = create_zone.index("array.push(used_supply_base_times, baseTime)")
        supply_created = create_zone.index("created := true", supply_db)
        if not (acceptance_gate < supply_db < supply_base_used < supply_created):
            raise AssertionError(f"{path.name}: supply base time must be reserved only after accepted zone creation")

        for needle in [
            "zoneSizeValid",
            "zTop := na\n                zBottom := na",
            "true  // No-op, keep current range",
        ]:
            if needle in create_zone:
                raise AssertionError(f"{path.name}: fixed pip-size creation filter must not suppress zones")

        forbidden = [
            "z.mitigated := true\n                    array.set(demandZones, i, z)\n                    db_updateZoneLiquidity(z)",
            "z.mitigated := true\n                    array.set(supplyZones, i, z)\n                    db_updateZoneLiquidity(z)",
        ]
        for needle in forbidden:
            if needle in strategy:
                raise AssertionError(f"{path.name}: found partial invalidation path")

    print("SND zone invalidation static contract passed")


if __name__ == "__main__":
    main()
