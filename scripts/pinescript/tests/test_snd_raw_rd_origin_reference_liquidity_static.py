from pathlib import Path


INDICATORS = [
    Path("scripts/pinescript/indicators/SND_Raw_RD_Forex.pine"),
    Path("scripts/pinescript/indicators/SND_Raw_RD_Forex_LAB.pine"),
    Path("scripts/pinescript/indicators/SND_Raw_RD_Forex_PROD.pine"),
]


def test_origin_formation_reference_liquidity_can_seed_zone_even_after_sweep_flag() -> None:
    for path in INDICATORS:
        source = path.read_text()

        assert 'showLiqDebug = input.bool(false, "Debug liquidity detection"' in source
        assert "referenceLiquidityCanSeedZone(RawZone z, int candidateBar, bool swept)" in source
        assert "candidateBar >= z.originBar - formationLegScanBars and candidateBar <= z.createdBar" in source
        assert "not swept or inOriginFormationWindow" in source
        assert "isDemandReference and referenceCanSeed" in source
        assert "not isDemandReference and referenceCanSeed" in source
        assert "REFERENCE_ALREADY_SWEPT" in source


def test_liquidity_debug_label_includes_origin_and_line_coordinates() -> None:
    for path in INDICATORS:
        source = path.read_text()

        assert "originHighValue(RawZone z)" in source
        assert "originLowValue(RawZone z)" in source
        assert "origin t" in source
        assert "zoneTop " in source
        assert " x1 " in source
        assert " x2 " in source
        assert "(showLiquidityCompareLabels or showLiqDebug or showInactiveZoneDebug)" in source
