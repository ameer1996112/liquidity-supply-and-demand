from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
INDICATOR = ROOT / "scripts/pinescript/indicators/SND_Raw_RD_Forex.pine"


def main() -> None:
    indicator = INDICATOR.read_text(encoding="utf-8")

    required = [
        'const string REJECT_HISTORICALLY_INVALID = "REJECT_HISTORICALLY_INVALID"',
        "zoneInvalidatedAfterOrigin(float top, float bottom, int baseIdx, bool demand) =>",
        "bool overlapsZone = high[offset] >= bottom and low[offset] <= top",
        "bool breaksZone = low[offset] < bottom or close[offset] < bottom",
        "bool breaksZone = high[offset] > top or close[offset] > top",
        "else if zoneInvalidatedAfterOrigin(top, bottom, baseIdx, demand)",
        "drawCandidateDiagnostic(demand, baseIdx, REJECT_HISTORICALLY_INVALID, effectiveModel)",
        'showMitigatedZones = input.bool(true, "Show Mitigated Zones")',
        'showUnlinkedCandidateZones = input.bool(false, "Show Unlinked Candidate Zones")',
        'showFreshStrategyZones = input.bool(true, "Show Fresh Strategy Zones")',
        'drawUnlinkedActiveZones() =>',
        'showUnlinkedCandidateZones or rawMode == "Detection Only" or rawMode == "Debug Selected Zone"',
        "isStrategyZoneModel(string model) =>",
        "zoneFillColorForZone(RawZone z) =>",
        "zoneFillColor(z.demand, z.model)",
        "zoneShouldHaveActiveBox(RawZone z) =>",
        "zoneHasPrimaryLiquidityEvidence(RawZone z) =>",
        "z.active and (z.liquidityLinked or zoneHasPrimaryLiquidityEvidence(z) or drawUnlinkedActiveZones())",
        "box b = drawUnlinkedActiveZones() ? createZoneBox(originBar, top, bottom, demand, effectiveModel) : na",
        'bool keepMitigatedZone = showMitigatedZones and z.inactiveReason == "MITIGATED_AFTER_SWEEP"',
        "else if keepMitigatedZone",
        "syncActiveZoneBox(z)",
        "hideInactiveZone(z)",
    ]

    for needle in required:
        if needle not in indicator:
            raise AssertionError(f"Missing raw historical invalidation marker: {needle}")

    creation_gate = indicator.index("else if zoneInvalidatedAfterOrigin(top, bottom, baseIdx, demand)")
    box_creation = indicator.index("box b = drawUnlinkedActiveZones() ? createZoneBox")
    if creation_gate > box_creation:
        raise AssertionError("Raw historical invalidation must run before drawing the zone box")

    forbidden = [
        "pendingStrategyColor",
        "pendingStrategyBorder",
        "createPendingStrategyZoneBox",
        "zoneUsesPendingStrategyColor",
    ]
    for needle in forbidden:
        if needle in indicator:
            raise AssertionError(f"Fresh zones must use demand/supply colors, found stale pending renderer: {needle}")

    print("SND Raw RD Forex historical invalidation static contract passed")


if __name__ == "__main__":
    main()
