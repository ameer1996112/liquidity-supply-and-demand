from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
INDICATORS = [
    ROOT / "scripts/pinescript/indicators/SND_Raw_RD_Forex.pine",
    ROOT / "scripts/pinescript/indicators/SND_Raw_RD_Forex_LAB.pine",
    ROOT / "scripts/pinescript/indicators/SND_Raw_RD_Forex_PROD.pine",
]


def _function_body(source: str, name: str, next_name: str) -> str:
    marker = f"{name}("
    start = source.index(marker)
    next_marker = f"\n{next_name}("
    end = source.index(next_marker, start)
    return source[start:end]


def test_nested_zone_cleanup_only_dedupes_same_formation_leg() -> None:
    for indicator_path in INDICATORS:
        source = indicator_path.read_text(encoding="utf-8")
        cleanup = _function_body(source, "cleanupNestedSameSideZones", "trimZones")

        assert "bool nearbySameLeg = math.abs(newZone.originBar - otherZone.originBar) <= formationLegScanBars" in cleanup
        assert "bool nestedSameLeg = nearbySameLeg and (newInsideOther or otherInsideNew)" in cleanup
        assert "bool heavyOverlap = nearbySameLeg and zoneOverlapPct" in cleanup
        assert "if nestedSameLeg or heavyOverlap" in cleanup
        assert "if newInsideOther or otherInsideNew or heavyOverlap" not in cleanup
