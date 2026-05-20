from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
STRATEGY = ROOT / "scripts/pinescript/strategies/SND_Strategy.pine"


def main() -> None:
    strategy = STRATEGY.read_text(encoding="utf-8")

    required = [
        "const float REDUNDANT_ZONE_GAP_ATR_MULT = 0.25",
        "zone_gap_between(float topA, float bottomA, float topB, float bottomB) =>",
        "zone_is_redundant_with_existing(float zTop, float zBottom, Core.Zone z) =>",
        "bool overlapsEnough = zone_overlap_pct(zTop, zBottom, z.top, z.bottom) >= duplicate_zone_overlap_pct",
        "float gap = zone_gap_between(zTop, zBottom, z.top, z.bottom)",
        "bool nearEnough = gap <= math.max(pip_size * MIN_DISTANCE_PIPS, nz(atr14, 0.0) * REDUNDANT_ZONE_GAP_ATR_MULT)",
        "overlapsEnough or nearEnough",
        'reason == "" or str.contains(reason, "WAITING_") or zone_is_overlap_visually_hidden(z)',
        "bool redundantZone = zone_is_redundant_with_existing(zTop, zBottom, z)",
        "if zone_duplicate_candidate(z) and redundantZone and z.top >= zTop",
        "if zone_duplicate_candidate(z) and redundantZone and zTop > z.top",
        'z.inactiveReason := "OVERLAP_VISUALLY_HIDDEN"',
    ]

    for needle in required:
        if needle not in strategy:
            raise AssertionError(f"Missing redundant zone contract marker: {needle}")

    forbidden = [
        "bool overlapsEnough = zone_overlap_pct(zTop, zBottom, z.top, z.bottom) >= duplicate_zone_overlap_pct\n                    if zone_duplicate_candidate(z) and overlapsEnough",
    ]

    for needle in forbidden:
        if needle in strategy:
            raise AssertionError(f"Redundant zone contract forbids overlap-only duplicate behavior: {needle}")

    print("SND redundant zone static contract passed")


if __name__ == "__main__":
    main()
