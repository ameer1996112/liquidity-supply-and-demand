from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
STRATEGY = ROOT / "scripts/pinescript/strategies/SND_Strategy.pine"


def _require(source: str, needles: list[str], label: str) -> None:
    missing = [needle for needle in needles if needle not in source]
    if missing:
        raise AssertionError(f"{label} missing:\n" + "\n".join(missing))


def main() -> None:
    strategy = STRATEGY.read_text(encoding="utf-8")

    _require(
        strategy,
        [
            "index_zone_displacement_confirmed(int displacementIdx, int baseIdx, bool isDemand) =>",
            "bool enabled = enable_continuation_zones and not is_index",
            "if not is_index",
            "result := true",
            "float index_min_close_extension_atr = 0.25",
            "float index_min_body_atr = 0.30",
            "float index_min_body_vs_base = 0.70",
            "bool closeExtensionOk = closeExtension >= atr14 * index_min_close_extension_atr",
            "bool bodyAtrOk = displacementBody >= atr14 * index_min_body_atr",
            "bool bodyVsBaseOk = baseRange <= 0 ? true : displacementBody >= baseRange * index_min_body_vs_base",
            "confirmStrengthOk = index_zone_displacement_confirmed(confirmIdx, baseIdx, isDemand)",
            "bool indexLegLengthOk = not is_index or leg >= 2",
            "displacementOk := displacementOk and index_zone_displacement_confirmed(displacementIdx, candidateBaseIdx, isDemand)",
            "if baseOk and indexLegLengthOk",
        ],
        "Index continuation/displacement strength gate",
    )

    print("SND index zone strength static contract passed")


if __name__ == "__main__":
    main()
