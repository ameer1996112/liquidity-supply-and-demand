from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
STRATEGY = ROOT / "scripts/pinescript/strategies/SND_Strategy.pine"


def _body(source: str, start_marker: str, end_marker: str) -> str:
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[start:end]


def _require(source: str, needles: list[str], label: str) -> None:
    missing = [needle for needle in needles if needle not in source]
    if missing:
        raise AssertionError(f"{label} missing:\n" + "\n".join(missing))


def main() -> None:
    strategy = STRATEGY.read_text(encoding="utf-8")
    origin_resolver = _body(
        strategy,
        "resolve_canonical_origin(int firstOriginIdx, bool isDemand) =>",
        "\ncreateZone(int baseIdx, bool isDemand",
    )
    create_zone = _body(
        strategy,
        "createZone(int baseIdx, bool isDemand",
        "\ngetLiquidityDistance(Core.Zone z, bool isSupply)",
    )

    _require(
        origin_resolver,
        [
            "int result = firstOriginIdx",
            "int scanIdx = firstOriginIdx + j",
            "bool scanOppositeOrigin = isDemand ? scan_close < scan_open : scan_close > scan_open",
            "if scanOppositeOrigin",
            "result := scanIdx",
            "break",
        ],
        "Canonical opposite-color origin resolver",
    )

    _require(
        create_zone,
        [
            "int originIdx = resolve_canonical_origin(baseIdx, isDemand)",
            "baseBarIdx = bar_index - originIdx",
            "int baseTime = time[originIdx]",
            "float baseHigh = high[originIdx]",
            "float baseLow  = low[originIdx]",
            "float baseOpen = open[originIdx]",
            "float baseClose = close[originIdx]",
            "int scanIdx = originIdx + j",
            "if use_fvg_confirmation and (originIdx - 2) >= 0",
            "int reactionIdx = originIdx - 1",
            "if high[originIdx] > high[reactionIdx]",
            "if low[originIdx] < low[reactionIdx]",
            "zone_invalidated_after_creation(zTop, zBottom, originIdx, isDemand)",
            "z.startTime := time[originIdx]",
            "Core.calculate_zone_score(isDemand, zTop, zBottom, originIdx",
        ],
        "Zone creation must use canonical origin for box and metadata",
    )

    print("SND origin selection static contract passed")


if __name__ == "__main__":
    main()
