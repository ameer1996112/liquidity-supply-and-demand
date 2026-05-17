from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
STRATEGY = ROOT / "scripts/pinescript/strategies/SND_Strategy.pine"


def _body(source: str, start_marker: str, end_marker: str) -> str:
    if start_marker not in source:
        return ""
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[start:end]


def _require(section: str, needles: list[str], label: str) -> None:
    missing = [needle for needle in needles if needle not in section]
    if missing:
        raise AssertionError(f"{label} missing:\n" + "\n".join(missing))


def _forbid(section: str, needles: list[str], label: str) -> None:
    present = [needle for needle in needles if needle in section]
    if present:
        raise AssertionError(f"{label} must not contain:\n" + "\n".join(present))


def main() -> None:
    strategy = STRATEGY.read_text(encoding="utf-8")
    entry_validation = _body(strategy, "validate_entry_conditions(bool isDemand, int idx) =>", "\nvar float[] _trade_entry_price")
    demand_lifecycle = _body(strategy, "if cached_demand_size > 0 and barstate.isconfirmed", "\nif cached_supply_size > 0 and barstate.isconfirmed")
    supply_lifecycle = _body(strategy, "if cached_supply_size > 0 and barstate.isconfirmed", "\nint demandSize = array.size(demandZones)")
    demand_cleanup = _body(strategy, "int demandSize = array.size(demandZones)", "\nint supplySize = array.size(supplyZones)")
    supply_cleanup = _body(strategy, "int supplySize = array.size(supplyZones)", "\nif show_zones")

    _require(
        strategy,
        [
            'const string REASON_PREFIX_STRUCT_INVALID = "STRUCT_INVALID:"',
            'const string REASON_PREFIX_ENTRY_BLOCKED = "ENTRY_BLOCKED:"',
            'const string REASON_PREFIX_MITIGATED = "MITIGATED:"',
            'const string REASON_STRUCT_DEMAND_DISTAL_CLOSE = "STRUCT_INVALID:DEMAND_DISTAL_CLOSE"',
            'const string REASON_STRUCT_DEMAND_DISTAL_WICK = "STRUCT_INVALID:DEMAND_DISTAL_WICK"',
            'const string REASON_STRUCT_SUPPLY_DISTAL_CLOSE = "STRUCT_INVALID:SUPPLY_DISTAL_CLOSE"',
            'const string REASON_STRUCT_SUPPLY_DISTAL_WICK = "STRUCT_INVALID:SUPPLY_DISTAL_WICK"',
            'const string REASON_ENTRY_RETURN_BEFORE_PROOF = "ENTRY_BLOCKED:RETURN_BEFORE_PROOF"',
            'const string REASON_ENTRY_WAITING_LIQUIDITY = "ENTRY_BLOCKED:WAITING_LIQUIDITY"',
            'const string REASON_ENTRY_WAITING_SWEEP = "ENTRY_BLOCKED:WAITING_SWEEP"',
            'const string REASON_ENTRY_WAITING_BOS = "ENTRY_BLOCKED:WAITING_BOS"',
            'const string REASON_MITIGATED_NO_ENTRY_CLOSE_INSIDE = "MITIGATED:NO_ENTRY_CLOSE_INSIDE"',
            'const string REASON_MITIGATED_USED_FOR_ENTRY = "MITIGATED:USED_FOR_ENTRY"',
            'const string REASON_EXPIRED = "EXPIRED"',
            'const string REASON_PRUNED = "PRUNED"',
            "zone_is_structural_invalid_reason(string reason) =>",
            "zone_is_entry_blocked_reason(string reason) =>",
            "zone_is_mitigated_reason(string reason) =>",
            'clean_zone_display = input.string("Trade Ready Only", "clean_zone_display", options=["Confirmed + Trade Ready", "Trade Ready Only"], group = "🎨 Display")',
            "zone_structurally_broken(Core.Zone z, bool isDemand) =>",
            "zone_trade_ready(Core.Zone z) =>",
            "zone_returned_to_zone(Core.Zone z, bool isDemand) =>",
            "zone_valid_rejection_return(Core.Zone z, bool isDemand) =>",
            "zone_close_inside(Core.Zone z, bool isDemand) =>",
            "zone_should_show_clean(Core.Zone z, bool isDemand) =>",
            "zone_should_show_lab(Core.Zone z, bool isDemand) =>",
        ],
        "Three-state reason model",
    )

    _require(
        entry_validation,
        [
            "bool entryTouchesZone = isDemand ? (low <= z.top and high >= z.bottom) : (high >= z.bottom and low <= z.top)",
            "bool entryDistalBreach = isDemand ? (close < z.bottom or (invalidate_on_wick and low < z.bottom)) : (close > z.top or (invalidate_on_wick and high > z.top))",
            "bool entryProofReady = z.liquidityValid and z.liquiditySwept and z.targetSwept",
            "if entryTouchesZone and not entryProofReady and not entryDistalBreach",
            "reason := REASON_ENTRY_RETURN_BEFORE_PROOF",
            "if canEnter and z.touchedPreSweep",
            "if canEnter and not zone_trade_ready(z)",
            "if canEnter and not zone_valid_rejection_return(z, isDemand)",
        ],
        "Entry eligibility contract",
    )

    _require(
        demand_lifecycle,
        [
            "bool closes_below_distal = close < z.bottom",
            "bool wicks_below_distal = low < z.bottom",
            "bool breaches_zone = closes_below_distal or (invalidate_on_wick and wicks_below_distal)",
            "if breaches_zone\n                        z.touchedPreSweep := true",
            "z.inactiveReason := REASON_ENTRY_RETURN_BEFORE_PROOF",
            "z.inactiveReason := REASON_MITIGATED_NO_ENTRY_CLOSE_INSIDE",
        ],
        "Demand lifecycle contract",
    )

    _require(
        supply_lifecycle,
        [
            "bool closes_above_distal = close > z.top",
            "bool wicks_above_distal = high > z.top",
            "bool breaches_zone = closes_above_distal or (invalidate_on_wick and wicks_above_distal)",
            "if breaches_zone\n                        z.touchedPreSweep := true",
            "z.inactiveReason := REASON_ENTRY_RETURN_BEFORE_PROOF",
            "z.inactiveReason := REASON_MITIGATED_NO_ENTRY_CLOSE_INSIDE",
        ],
        "Supply lifecycle contract",
    )

    _require(
        demand_cleanup,
        [
            "bool close_below_zone     = current_close < z.bottom",
            "bool wick_below_zone = current_low < z.bottom",
            "if close_below_zone or isTooOld or (invalidate_on_wick and wick_below_zone)",
            "string demandStructuralReason = isTooOld ? REASON_EXPIRED : (close_below_zone ? REASON_STRUCT_DEMAND_DISTAL_CLOSE : REASON_STRUCT_DEMAND_DISTAL_WICK)",
            "remove_zone_all_arrays(true, i, demandStructuralReason)",
        ],
        "Demand structural invalidation contract",
    )

    _require(
        supply_cleanup,
        [
            "bool close_above_zone     = current_close > z.top",
            "bool wick_above_zone = current_high > z.top",
            "if close_above_zone or isTooOld or (invalidate_on_wick and wick_above_zone)",
            "string supplyStructuralReason = isTooOld ? REASON_EXPIRED : (close_above_zone ? REASON_STRUCT_SUPPLY_DISTAL_CLOSE : REASON_STRUCT_SUPPLY_DISTAL_WICK)",
            "remove_zone_all_arrays(false, i, supplyStructuralReason)",
        ],
        "Supply structural invalidation contract",
    )

    _require(
        strategy,
        [
            "z.inactiveReason := REASON_MITIGATED_USED_FOR_ENTRY",
            "db_updateZoneLiquidity(z)",
        ],
        "Mitigated/consumed contract",
    )

    _forbid(
        strategy,
        [
            "INVALID_RETURN_BEFORE_PROOF",
            "INVALID_CLOSE_INSIDE_ZONE",
            "Zone touched before liquidity sweep",
            "if close_inside_demand or",
            "if close_inside_supply or",
        ],
        "Structural invalidation split",
    )

    print("SND zone rule static contract passed")


if __name__ == "__main__":
    main()
