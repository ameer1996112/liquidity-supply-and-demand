from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
STRATEGIES = [
    ROOT / "scripts/pinescript/strategies/SND_Strategy.pine",
    ROOT / "scripts/pinescript/strategies/SND_Strategey_refactor.pine",
]


def _body(source: str, start_marker: str, end_marker: str) -> str:
    start = source.index(start_marker)
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
            "if cached_demand_size > 0 and barstate.isconfirmed",
            "if cached_supply_size > 0 and barstate.isconfirmed",
        )
        for needle in [
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

        supply_lifecycle = _body(
            strategy,
            "if cached_supply_size > 0 and barstate.isconfirmed",
            "int demandSize = array.size(demandZones)",
        )
        for needle in [
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

        for needle in [
            "if close_below_zone or isTooOld or (invalidate_on_wick and wick_below_zone)",
            "if close_above_zone or isTooOld or (invalidate_on_wick and wick_above_zone)",
        ]:
            if needle not in strategy:
                raise AssertionError(f"{path.name}: distal structural invalidation contract missing {needle!r}")

        for label, lifecycle in [
            ("demand", demand_lifecycle),
            ("supply", supply_lifecycle),
        ]:
            if "if z.isHistorical\n                continue" in lifecycle:
                raise AssertionError(f"{path.name}: {label} historical zones must still run invalidation lifecycle")

        create_zone = _body(
            strategy,
            "createZone(int baseIdx, bool isDemand, bool isHistorical, int candlesInBase, int legCandles, int zoneUZID) =>",
            "\nremove_zone_all_arrays(",
        )
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
