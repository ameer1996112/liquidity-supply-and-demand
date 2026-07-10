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
        assert "bool nestedConflict = (newInsideOther or otherInsideNew) and sameModelFamily(newZone.model, otherZone.model)" in cleanup
        assert "bool nestedSameLeg = nestedConflict and nearbySameLeg" in cleanup
        assert "bool newIsParent = otherInsideNew" in cleanup
        assert "bool heavyOverlap = nearbySameLeg and zoneOverlapPct(newZone.top, newZone.bottom, otherZone.top, otherZone.bottom) >= 0.65" in cleanup
        assert "bool keepNew = nestedConflict ? (nestedSameLeg ? zoneSize(newZone.top, newZone.bottom) < zoneSize(otherZone.top, otherZone.bottom) : newIsParent) : preferFirstZone(newZone, otherZone)" in cleanup
        assert "sameOriginNested" not in cleanup
        assert "adjacentSameLegOrigin" not in cleanup
        assert "if nestedConflict or heavyOverlap" in cleanup
        assert "if newInsideOther or otherInsideNew or heavyOverlap" not in cleanup
